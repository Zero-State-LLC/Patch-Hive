"""Spec 002 (patch book publishing) T010: the publication lifecycle transitions table.

The table below is checked against specs/002-patch-book-publishing/spec.md, "Stateful behavior",
"Publication lifecycle machine". Any (state, event) pair it does not list must be rejected
and leave the publication unchanged (the rule at the top of that section; SC-007).

The global guard (every event except ``account_deleted`` requires
``ENABLE_LEGACY_PUBLISHING=true``) is encoded by firing each event at an app that main.py builds
with the flag off. The page and book compile machines aren't built (owner decision 37), so
they aren't encoded here.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import main
from account.deletion import anonymize_user
from admin.models import AdminAuditLog
from community.models import User
from core import get_db, settings
from main import app
from patches.models import Patch
from publishing.models import Export, Publication, PublicationReport
from racks.models import Rack
from tests.conftest import bearer_headers

BACKEND = Path(__file__).resolve().parents[2]
SPEC = BACKEND.parent / "specs" / "002-patch-book-publishing" / "spec.md"

# Spec "Publication lifecycle machine" / the transitions table: (from, event, to).
SPEC_TRANSITIONS = [
    ("[*]", "create", "draft"),
    ("draft", "publish", "published"),
    ("published", "owner_hide", "hidden"),
    ("hidden", "owner_unhide", "published"),
    ("published", "admin_hide", "hidden"),
    ("hidden", "admin_hide", "hidden"),
    ("published", "admin_remove", "removed"),
    ("hidden", "admin_remove", "removed"),
    ("draft", "edit_metadata", "draft"),
    ("published", "edit_metadata", "published"),
    ("hidden", "edit_metadata", "hidden"),
    ("published", "report", "published"),
    ("published", "owner_set_same", "published"),
    ("hidden", "owner_set_same", "hidden"),
    ("draft", "account_deleted", "removed"),
    ("published", "account_deleted", "removed"),
    ("hidden", "account_deleted", "removed"),
    ("removed", "account_deleted", "removed"),
]
# Rows that have no route to fire through LISTED, and the test that holds each one.
HELD_BY = {
    ("[*]", "create", "draft"): "test_create_makes_a_draft_and_a_second_create_is_rejected",
    ("draft", "publish", "published"): "test_publish_of_a_draft_is_refused_without_a_validated_book",
    ("draft", "account_deleted", "removed"): "test_closing_an_account_removes_the_publication",
    ("published", "account_deleted", "removed"): "test_closing_an_account_removes_the_publication",
    ("hidden", "account_deleted", "removed"): "test_closing_an_account_removes_the_publication",
    ("removed", "account_deleted", "removed"): "test_closing_an_account_removes_the_publication",
}
# The row FR-048 keeps from succeeding until T033: no export is bound to a validated book.
CANNOT_SUCCEED_YET = {("draft", "publish", "published")}

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
    # hidden --admin_hide--> hidden, when the owner hid it first (D6)
    ("hidden", False, "admin_hide", 200, "hidden"),
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
    # setting the status a publication already has changes nothing (D9)
    ("published", False, "owner_unhide", 200, "published"),
    ("hidden", False, "owner_hide", 200, "hidden"),
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
    ("hidden", True, "admin_hide", 409),  # already held; would replace the audit link (D6)
    ("hidden", True, "owner_unhide", 409),  # moderation-hidden (OQ-2)
    ("hidden", True, "owner_hide", 409),  # no no-op under a hold
]

# Spec "Illegal transitions": any event while ENABLE_LEGACY_PUBLISHING is off. Every listed
# (from, event) pair, plus `draft --publish-->` (PATCH status=published, fired as owner_unhide).
FLAG_OFF = sorted(
    {(start, moderated, event) for start, moderated, event, _, _ in LISTED}
    | {("draft", False, "owner_unhide")}
)


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def flag_off_client(db_session: Session, monkeypatch):
    """The app as main.py builds it with ENABLE_LEGACY_PUBLISHING off.

    main.py mounts the publishing router at import time, and the suite runs with the flag on
    (tests/conftest.py), so a second copy of main.py is loaded with the flag patched off.
    """
    monkeypatch.setattr(settings, "enable_legacy_publishing", False)
    spec = importlib.util.spec_from_file_location("main_publishing_off", main.__file__)
    flag_off = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flag_off)

    def override_get_db():
        yield db_session

    flag_off.app.dependency_overrides[get_db] = override_get_db
    yield TestClient(flag_off.app)


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


def _spec_rows() -> list[tuple[str, str, str]]:
    machine = SPEC.read_text(encoding="utf-8").split("### Publication lifecycle machine")[1]
    table = machine.split("Illegal transitions:")[0]
    rows = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \| .*? \| `([^`]+)` \| ", table, re.M)
    return [(start, event, end) for start, event, end in rows]


def test_this_file_encodes_the_table_in_the_spec():
    assert sorted(_spec_rows()) == sorted(SPEC_TRANSITIONS)


def test_every_row_has_a_test():
    fired = {(start, event, end) for start, _, event, _, end in LISTED}
    fired = {
        (start, "owner_set_same" if start == end and event.startswith("owner") else event, end)
        for start, event, end in fired
    }
    assert set(SPEC_TRANSITIONS) - fired == set(HELD_BY)
    for test in HELD_BY.values():
        assert test in globals()
    assert CANNOT_SUCCEED_YET <= set(HELD_BY)


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


@pytest.mark.parametrize(("start", "moderated", "event"), FLAG_OFF)
def test_event_with_the_flag_off_is_404_without_change(
    flag_off_client, db_session, world, start, moderated, event
):
    pub = _publication(db_session, world, start, moderated)
    audit_before = pub.moderation_audit_id
    resp = _fire(flag_off_client, world, pub, event)
    assert resp.status_code == 404, resp.text
    db_session.refresh(pub)
    assert pub.status == start
    assert pub.title == "Before"
    assert pub.moderation_audit_id == audit_before
    assert pub.removed_reason is None
    assert _reports(db_session, pub) == 0


def test_create_with_the_flag_off_is_404_and_writes_nothing(flag_off_client, db_session, world):
    export = _export(db_session, world["owner"], world["patch"])
    body = {"export_id": export.id, "title": "Mine", "visibility": "public",
            "allow_download": True, "allow_remix": False}
    resp = flag_off_client.post(
        "/api/me/publications", json=body, headers=bearer_headers(world["owner"])
    )
    assert resp.status_code == 404, resp.text
    assert db_session.query(Publication).filter_by(export_id=export.id).count() == 0


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


def test_an_owner_cannot_unhide_after_an_admin_acted_second(client, db_session, world):
    pub = _publication(db_session, world, "published", False)
    assert _fire(client, world, pub, "owner_hide").status_code == 200
    assert _fire(client, world, pub, "admin_hide").status_code == 200

    resp = _fire(client, world, pub, "owner_unhide")

    assert resp.status_code == 409
    assert resp.json()["detail"] == "PUBLICATION_UNDER_MODERATION"
    db_session.refresh(pub)
    assert pub.status == "hidden"


@pytest.mark.parametrize("state", STATES)
def test_closing_an_account_removes_the_publication(db_session, world, state):
    """D2: this is the one way out of a state that skips the owner and admin routes, so it isn't
    a moderation action: it writes no audit link, and it keeps one that's already there."""
    pub = _publication(db_session, world, state, False)

    anonymize_user(db_session, world["owner"])
    db_session.commit()

    db_session.refresh(pub)
    assert pub.status == "removed"
    assert pub.removed_reason == "ACCOUNT_DELETED"
    assert pub.moderation_audit_id is None
    assert pub.title == "Removed" and pub.description is None
    assert pub.allow_download is False


def test_closing_an_account_keeps_a_moderation_link(db_session, world):
    pub = _publication(db_session, world, "hidden", True)
    audit_before = pub.moderation_audit_id

    anonymize_user(db_session, world["owner"])
    db_session.commit()

    db_session.refresh(pub)
    assert pub.status == "removed" and pub.moderation_audit_id == audit_before


@pytest.mark.parametrize("state", ["draft", "hidden", "removed"])
def test_only_a_published_row_can_be_read_or_downloaded(client, db_session, world, state):
    """FR-043, FR-046: a row that isn't public looks the same as a row that doesn't exist."""
    pub = _publication(db_session, world, state, False)
    assert client.get(f"/api/p/{pub.slug}").status_code == 404
    assert client.get(f"/api/p/{pub.slug}/download/pdf").status_code == 404


def test_the_gallery_lists_only_published_public_rows(client, db_session, world):
    rows = {state: _publication(db_session, world, state, False) for state in STATES}
    unlisted = _publication(db_session, world, "published", False)
    unlisted.visibility = "unlisted"
    db_session.commit()

    resp = client.get("/api/gallery/publications")

    assert resp.status_code == 200
    assert [card["slug"] for card in resp.json()["publications"]] == [rows["published"].slug]


def test_the_two_exports_paths_stay_closed_with_the_flag_off(flag_off_client, db_session, world):
    """D1: the account router owns /me/exports, so these two aren't 404. No publishing handler
    runs: POST has no route, and GET lists paid exports, not publication exports."""
    _export(db_session, world["owner"], world["patch"])
    owner = bearer_headers(world["owner"])
    before = db_session.query(Export).count()

    posted = flag_off_client.post(
        "/api/me/exports", json={"export_type": "patch", "patch_id": world["patch"].id}, headers=owner
    )
    listed = flag_off_client.get("/api/me/exports", headers=owner)

    assert posted.status_code == 405
    assert listed.status_code == 200 and listed.json() == []
    assert db_session.query(Export).count() == before


def test_only_the_lifecycle_routes_and_account_closure_write_a_status():
    """FR-049: no model or decision-layer code changes a status or moderates."""
    writers = set()
    for path in BACKEND.rglob("*.py"):
        if "tests" in path.parts or "alembic" in path.parts:
            continue
        if re.search(r"\bpublication\.status\s*=[^=]", path.read_text(encoding="utf-8")):
            writers.add(path.relative_to(BACKEND).as_posix())
    assert writers == {"publishing/routes.py", "account/deletion.py"}

    import_line = re.compile(r"^\s*(?:from|import)\s+(\w+)", re.M)
    for path in (BACKEND / "intelligence").rglob("*.py"):
        assert "publishing" not in import_line.findall(path.read_text(encoding="utf-8")), path
    for path in (BACKEND / "publishing").rglob("*.py"):
        assert "intelligence" not in import_line.findall(path.read_text(encoding="utf-8")), path
