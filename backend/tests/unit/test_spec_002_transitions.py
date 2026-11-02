"""Spec 002 (patch book publishing) T010: the publication lifecycle transitions table.

The table below is copied from specs/002-patch-book-publishing/spec.md, "Stateful behavior",
"Publication lifecycle machine". Any (state, event) pair it does not list must be rejected
and leave the publication unchanged (the rule at the top of that section; SC-007).

The page compilation machine and the book compilation machine have no implementation in the
backend (no stage states, events or guards exist in code), so they are not encoded here.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from community.models import User
from core import get_db
from main import app
from patches.models import Patch
from publishing.models import Export, Publication, PublicationReport
from racks.models import Rack
from tests.conftest import bearer_headers

STATES = ("draft", "published", "hidden", "removed")

# Publication lifecycle machine. (from, event) -> (guard-met outcome).
# Each row: (from, moderation_hidden, event, expected http status, to).
LISTED = [
    # published --owner_hide--> hidden
    ("published", False, "owner_hide", 200, "hidden"),
    # hidden --owner_unhide--> published (not hidden by moderation)
    ("hidden", False, "owner_unhide", 200, "published"),
    # published --admin_hide--> hidden
    ("published", False, "admin_hide", 200, "hidden"),
    # published/hidden --admin_remove--> removed
    ("published", False, "admin_remove", 200, "removed"),
    ("hidden", False, "admin_remove", 200, "removed"),
    ("hidden", True, "admin_remove", 200, "removed"),
    # edit_metadata keeps the state in draft, published and hidden
    ("draft", False, "edit_metadata", 200, "draft"),
    ("published", False, "edit_metadata", 200, "published"),
    ("hidden", False, "edit_metadata", 200, "hidden"),
    # published --report--> published
    ("published", False, "report", 201, "published"),
]

# Spec "Illegal transitions" plus the unlisted pairs; each is rejected, state unchanged.
ILLEGAL = [
    ("removed", False, "owner_hide", 409),
    ("removed", False, "owner_unhide", 409),
    ("removed", False, "admin_hide", 409),
    ("removed", False, "admin_remove", 409),
    ("removed", False, "edit_metadata", 409),
    ("removed", False, "report", 404),
    ("draft", False, "owner_hide", 409),  # draft -> hidden
    ("draft", False, "owner_unhide", 409),
    ("draft", False, "admin_hide", 409),
    ("draft", False, "admin_remove", 409),  # draft -> removed (OQ-3)
    ("draft", False, "report", 404),
    ("hidden", False, "report", 404),
    ("hidden", False, "admin_hide", 409),
    ("hidden", True, "owner_unhide", 409),  # moderation-hidden (OQ-2)
    ("published", False, "owner_unhide", 200),  # same status is a no-op, see below
]
# The last row is a no-op re-set of "published", not an illegal pair: drop it.
ILLEGAL = ILLEGAL[:-1]


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def world(db_session: Session, sample_user: User, sample_case):
    admin = User(username="adm", email="adm@example.com", password_hash="h", is_admin=True)
    stranger = User(username="stranger", email="s@example.com", password_hash="h")
    db_session.add_all([admin, stranger])
    rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
    db_session.add(rack)
    db_session.commit()
    patch = Patch(
        rack_id=rack.id, name="P", category="Voice", connections=[],
        generation_seed=1, generation_version="1.0",
    )
    db_session.add(patch)
    db_session.commit()
    return {"owner": sample_user, "admin": admin, "stranger": stranger, "patch": patch}


def _export(db: Session, owner: User, patch: Patch) -> Export:
    export = Export(
        owner_user_id=owner.id, patch_id=patch.id, export_type="patch",
        license="CC BY-NC 4.0", run_id="run", generated_at=datetime.utcnow(),
        patch_count=1, manifest_hash="h", artifact_urls={},
    )
    db.add(export)
    db.commit()
    return export


def _publication(db: Session, world: dict, state: str, moderated: bool) -> Publication:
    export = _export(db, world["owner"], world["patch"])
    pub = Publication(
        export_id=export.id, publisher_user_id=world["owner"].id, slug=f"pub-{export.id}",
        visibility="public", status=state, allow_download=True, allow_remix=False,
        title="Before", description="d", published_at=datetime.utcnow(),
    )
    db.add(pub)
    db.commit()
    if moderated:
        audit = AdminAuditLog(
            actor_user_id=world["admin"].id, actor_role="Admin",
            action_type="hide_publication", target_type="publication", target_id=str(pub.id),
        )
        db.add(audit)
        db.flush()
        pub.moderation_audit_id = audit.id
        db.commit()
    return pub


def _fire(client: TestClient, world: dict, pub: Publication, event: str):
    owner = bearer_headers(world["owner"])
    admin = bearer_headers(world["admin"])
    own = f"/api/me/publications/{pub.id}"
    adm = f"/api/admin/publications/{pub.id}"
    reason = {"reason": "Policy"}
    if event == "owner_hide":
        return client.patch(own, json={"status": "hidden"}, headers=owner)
    if event == "owner_unhide":
        return client.patch(own, json={"status": "published"}, headers=owner)
    if event == "edit_metadata":
        return client.patch(own, json={"title": "After"}, headers=owner)
    if event == "admin_hide":
        return client.post(f"{adm}/hide", json=reason, headers=admin)
    if event == "admin_remove":
        return client.post(f"{adm}/remove", json=reason, headers=admin)
    if event == "report":
        return client.post(f"/api/p/{pub.slug}/report", json={"reason": "spam"})
    raise AssertionError(event)


def _reports(db: Session, pub: Publication) -> int:
    return db.query(PublicationReport).filter_by(publication_id=pub.id).count()


@pytest.mark.parametrize(("start", "moderated", "event", "code", "end"), LISTED)
def test_listed_transition(client, db_session, world, start, moderated, event, code, end):
    pub = _publication(db_session, world, start, moderated)
    resp = _fire(client, world, pub, event)
    assert resp.status_code == code, resp.text
    db_session.refresh(pub)
    assert pub.status == end
    if event == "edit_metadata":
        assert pub.title == "After"
    if event in ("admin_hide", "admin_remove"):
        assert pub.moderation_audit_id is not None
    if event == "admin_remove":
        assert pub.removed_reason == "Policy"
    if event == "report":
        assert _reports(db_session, pub) == 1


@pytest.mark.parametrize(("start", "moderated", "event", "code"), ILLEGAL)
def test_illegal_transition_is_rejected_without_change(
    client, db_session, world, start, moderated, event, code
):
    pub = _publication(db_session, world, start, moderated)
    audit_before = pub.moderation_audit_id
    resp = _fire(client, world, pub, event)
    assert resp.status_code == code, resp.text
    db_session.refresh(pub)
    assert pub.status == start
    assert pub.title == "Before"
    assert pub.moderation_audit_id == audit_before
    assert pub.removed_reason is None
    assert _reports(db_session, pub) == 0


def test_create_makes_a_draft_and_a_second_create_is_rejected(client, db_session, world):
    export = _export(db_session, world["owner"], world["patch"])
    body = {"export_id": export.id, "title": "Mine", "visibility": "public",
            "allow_download": True, "allow_remix": False}
    owner = bearer_headers(world["owner"])
    first = client.post("/api/me/publications", json=body, headers=owner)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "draft"
    second = client.post("/api/me/publications", json=body, headers=owner)
    assert second.status_code == 400
    assert db_session.query(Publication).filter_by(export_id=export.id).count() == 1


def test_create_by_non_owner_of_the_export_is_rejected(client, db_session, world):
    export = _export(db_session, world["owner"], world["patch"])
    body = {"export_id": export.id, "title": "Mine", "visibility": "public",
            "allow_download": True, "allow_remix": False}
    resp = client.post("/api/me/publications", json=body, headers=bearer_headers(world["stranger"]))
    assert resp.status_code == 403
    assert db_session.query(Publication).filter_by(export_id=export.id).count() == 0


def test_publish_of_a_draft_is_refused_without_a_validated_book(client, db_session, world):
    """Listed `draft --publish--> published` is guarded by FR-048; no export qualifies today."""
    pub = _publication(db_session, world, "draft", False)
    resp = _fire(client, world, pub, "owner_unhide")  # PATCH status=published
    assert resp.status_code == 409
    assert resp.json()["detail"] == "PUBLICATION_BOOK_NOT_VALIDATED"
    db_session.refresh(pub)
    assert pub.status == "draft"


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("target", ["draft", "removed"])
def test_owner_patch_to_draft_or_removed_is_rejected(client, db_session, world, state, target):
    pub = _publication(db_session, world, state, False)
    resp = client.patch(
        f"/api/me/publications/{pub.id}", json={"status": target},
        headers=bearer_headers(world["owner"]),
    )
    assert resp.status_code == 422  # the schema accepts only published or hidden
    db_session.refresh(pub)
    assert pub.status == state


@pytest.mark.parametrize("state", STATES)
def test_owner_event_from_someone_else_is_rejected(client, db_session, world, state):
    pub = _publication(db_session, world, state, False)
    resp = client.patch(
        f"/api/me/publications/{pub.id}", json={"status": "hidden", "title": "Hijack"},
        headers=bearer_headers(world["stranger"]),
    )
    assert resp.status_code == 404
    db_session.refresh(pub)
    assert pub.status == state and pub.title == "Before"


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("action", ["hide", "remove"])
def test_admin_event_from_a_non_admin_is_rejected(client, db_session, world, state, action):
    pub = _publication(db_session, world, state, False)
    resp = client.post(
        f"/api/admin/publications/{pub.id}/{action}", json={"reason": "x"},
        headers=bearer_headers(world["owner"]),
    )
    assert resp.status_code == 403
    db_session.refresh(pub)
    assert pub.status == state and pub.moderation_audit_id is None
