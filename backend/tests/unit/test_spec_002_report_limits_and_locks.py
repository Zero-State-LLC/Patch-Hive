"""Spec 002 OQ-10 (row lock on owner and admin transitions) and OQ-13 (report limits).

OQ-10: the row lock is SELECT ... FOR UPDATE, a no-op on SQLite, so the test here covers
the part SQLite can show: the owner path reads the moderation state fresh, never a stale
copy already held in the session.
OQ-13: anonymous reports stay allowed, are rate-limited per client address, and a signed-in
reporter can report a publication only once. Retention stays undecided.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from community import login_guard
from community.models import User
from publishing import routes
from publishing.models import Publication, PublicationReport
from tests.conftest import bearer_headers
from tests.unit.test_spec_002_transitions import _publication, client, world  # noqa: F401


def _count(db: Session, pub: Publication, **filters) -> int:
    return (
        db.query(PublicationReport)
        .filter(PublicationReport.publication_id == pub.id)
        .filter_by(**filters)
        .count()
    )


def test_owner_patch_sees_admin_hide_made_after_the_row_was_loaded(client, db_session, world):  # noqa: F811
    pub = _publication(db_session, world, "published", False)
    assert pub.moderation_audit_id is None  # the session now holds this row as unmoderated
    audit_id = db_session.execute(
        text(
            "INSERT INTO admin_audit_log (actor_user_id, actor_role, action_type, target_type, "
            "target_id, created_at) VALUES (:a, 'Admin', 'hide_publication', 'publication', "
            ":t, CURRENT_TIMESTAMP) RETURNING id"
        ),
        {"a": world["admin"].id, "t": str(pub.id)},
    ).scalar_one()
    db_session.execute(
        text("UPDATE publications SET status='hidden', moderation_audit_id=:m WHERE id=:i"),
        {"m": audit_id, "i": pub.id},
    )
    db_session.commit()

    response = client.patch(
        f"/api/me/publications/{pub.id}",
        json={"status": "published"},
        headers=bearer_headers(world["owner"]),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "PUBLICATION_UNDER_MODERATION"


def test_anonymous_reports_are_rate_limited_per_client(client, db_session, world, monkeypatch):  # noqa: F811
    monkeypatch.setattr(routes, "REPORT_ATTEMPTS", 2)
    pub = _publication(db_session, world, "published", False)
    url = f"/api/p/{pub.slug}/report"
    body = {"reason": "Spam"}

    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 201
    third = client.post(url, json=body)

    assert third.status_code == 429
    assert third.json()["detail"] == "REPORT_RATE_LIMIT"
    assert _count(db_session, pub, reporter_user_id=None) == 2


def test_rate_limit_is_per_address(client, db_session, world, monkeypatch):  # noqa: F811
    monkeypatch.setattr(routes, "REPORT_ATTEMPTS", 1)
    pub = _publication(db_session, world, "published", False)
    url = f"/api/p/{pub.slug}/report"

    first = client.post(url, json={"reason": "Spam"}, headers={"x-forwarded-for": "198.51.100.1"})
    again = client.post(url, json={"reason": "Spam"}, headers={"x-forwarded-for": "198.51.100.1"})
    other = client.post(url, json={"reason": "Spam"}, headers={"x-forwarded-for": "198.51.100.2"})

    assert (first.status_code, again.status_code, other.status_code) == (201, 429, 201)


def test_signed_in_reporter_is_deduplicated_per_publication(client, db_session, world):  # noqa: F811
    pub = _publication(db_session, world, "published", False)
    other_pub = _publication(db_session, world, "published", False)
    headers = bearer_headers(world["stranger"])
    body = {"reason": "Spam"}

    first = client.post(f"/api/p/{pub.slug}/report", json=body, headers=headers)
    second = client.post(f"/api/p/{pub.slug}/report", json={"reason": "Again"}, headers=headers)
    elsewhere = client.post(f"/api/p/{other_pub.slug}/report", json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == {"status": "already_reported"}
    assert elsewhere.status_code == 201
    assert _count(db_session, pub, reporter_user_id=world["stranger"].id) == 1
    assert _count(db_session, other_pub, reporter_user_id=world["stranger"].id) == 1


def test_different_signed_in_reporters_each_get_one_report(client, db_session, world):  # noqa: F811
    pub = _publication(db_session, world, "published", False)
    url = f"/api/p/{pub.slug}/report"
    admin = db_session.get(User, world["admin"].id)

    a = client.post(url, json={"reason": "Spam"}, headers=bearer_headers(world["stranger"]))
    b = client.post(url, json={"reason": "Spam"}, headers=bearer_headers(admin))

    assert (a.status_code, b.status_code) == (201, 201)
    assert _count(db_session, pub) == 2


def test_report_limit_resets_with_the_guard(client, db_session, world, monkeypatch):  # noqa: F811
    monkeypatch.setattr(routes, "REPORT_ATTEMPTS", 1)
    pub = _publication(db_session, world, "published", False)
    url = f"/api/p/{pub.slug}/report"
    assert client.post(url, json={"reason": "Spam"}).status_code == 201
    assert client.post(url, json={"reason": "Spam"}).status_code == 429

    login_guard.reset_attempts()

    assert client.post(url, json={"reason": "Spam"}).status_code == 201
