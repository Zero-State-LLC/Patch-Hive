"""
Account deletion anonymizes the user and keeps ledger and referral rows
(spec 004 OQ-12, EC-8; decided ``A_anonymize_keep``).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from account.models import AccountReferral, CreditLedgerEntry
from admin.models import AdminAuditLog
from canon.models import (
    CanonicalCreditLedgerEntryRecord,
    ImageAssetRecord,
    PatchUserOverlayRecord,
    UserStyleRecipeRecord,
)
from cases.models import Case
from community.models import Comment, RefreshToken, User, Vote
from core.security import get_password_hash
from main import app
from monetization.models import CreditsLedger, Referral
from patches.models import Patch  # noqa: F401  (Comment/Vote relationships)
from publishing.models import Publication, PublicationExport, PublicationReport
from racks.models import Rack
from tests.conftest import make_user

PASSWORD = "correct horse battery"


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _with_password(db: Session, user: User) -> User:
    user.password_hash = get_password_hash(PASSWORD)
    user.bio = f"{user.username} bio"
    user.avatar_url = f"https://img.example.com/{user.username}.png"
    db.commit()
    return user


def _rack(db: Session, owner: User, case: Case, name: str) -> Rack:
    rack = Rack(user_id=owner.id, case_id=case.id, name=name, description="my studio", is_public=True)
    db.add(rack)
    db.commit()
    return rack


def _image(db: Session, owner: User, rack: Rack, path: Path, digest: str) -> ImageAssetRecord:
    path.write_bytes(b"jpeg")
    now = datetime.now(timezone.utc)
    record = ImageAssetRecord(
        id=f"img-{owner.username}", rack_id=rack.id, user_id=owner.id, content_sha256=digest,
        media_type="image/jpeg", width=1, height=1, byte_length=4, storage_path=str(path),
        retention_days=30, retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False, created_at=now,
    )
    db.add(record)
    db.commit()
    return record


def _publication(db: Session, owner: User, slug: str) -> Publication:
    export = PublicationExport(
        owner_user_id=owner.id, export_type="rack", license="CC BY-NC 4.0", run_id="run",
        generated_at=datetime.utcnow(), manifest_hash="h", artifact_urls={},
    )
    db.add(export)
    db.flush()
    publication = Publication(
        export_id=export.id, publisher_user_id=owner.id, slug=slug, visibility="public",
        status="published", title=f"{owner.username}'s patches", description="about me",
        cover_image_url="https://img.example.com/cover.png", published_at=datetime.utcnow(),
    )
    db.add(publication)
    db.commit()
    return publication


@pytest.fixture
def world(db_session: Session, sample_case: Case, tmp_path: Path) -> dict:
    db = db_session
    referrer = _with_password(db, make_user(db, "referrer"))
    member = _with_password(db, make_user(db, "member"))
    other = _with_password(db, make_user(db, "other"))
    member.referred_by = referrer.id
    db.commit()

    # Financial and referral records, which must survive.
    db.add_all([
        Referral(referrer_user_id=referrer.id, referred_user_id=member.id, status="Pending"),
        AccountReferral(referrer_user_id=referrer.id, referred_user_id=member.id),
        CanonicalCreditLedgerEntryRecord(
            id="grant-member", user_id=member.id, delta=10, entry_type="grant",
            idempotency_key="admin-grant:member", created_at=datetime.now(timezone.utc),
        ),
        CreditsLedger(user_id=member.id, change_type="Grant", credits_delta=5),
        CreditLedgerEntry(user_id=member.id, entry_type="Grant", amount=5),
    ])
    db.commit()

    # Personal content of the member and of another user.
    member_rack = _rack(db, member, sample_case, "Member Rack")
    other_rack = _rack(db, other, sample_case, "Other Rack")
    member_image = _image(db, member, member_rack, tmp_path / "member.jpg", "a" * 64)
    other_image = _image(db, other, other_rack, tmp_path / "other.jpg", "b" * 64)
    member_pub = _publication(db, member, "member-pub")
    other_pub = _publication(db, other, "other-pub")
    now = datetime.now(timezone.utc)
    db.add_all([
        Comment(user_id=member.id, rack_id=other_rack.id, content="nice rack"),
        Comment(user_id=other.id, rack_id=member_rack.id, content="thanks"),
        Vote(user_id=member.id, rack_id=other_rack.id),
        PatchUserOverlayRecord(id="ov-member", user_id=member.id, patch_ref="legacy-patch-1", notes="mine"),
        PatchUserOverlayRecord(id="ov-other", user_id=other.id, patch_ref="legacy-patch-1", notes="theirs"),
        UserStyleRecipeRecord(
            id="recipe-member", user_id=member.id, name="dark", recipe_json={}, recipe_hash="r" * 64,
            created_at=now, updated_at=now,
        ),
        PublicationReport(publication_id=other_pub.id, reporter_user_id=member.id, reason="spam"),
    ])
    db.commit()
    return {
        "referrer": referrer, "member": member, "other": other,
        "member_rack": member_rack, "other_rack": other_rack,
        "member_image": member_image, "other_image": other_image,
        "member_pub": member_pub, "other_pub": other_pub,
    }


def _sign_in(client: TestClient, username: str) -> str:
    resp = client.post("/api/community/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _delete(client: TestClient, token: str, password: str = PASSWORD):
    return client.request(
        "DELETE", "/api/me", json={"password": password}, headers={"Authorization": f"Bearer {token}"}
    )


def test_delete_requires_sign_in(client: TestClient, world: dict) -> None:
    assert client.request("DELETE", "/api/me", json={"password": PASSWORD}).status_code == 401


def test_wrong_password_is_refused_and_changes_nothing(
    client: TestClient, db_session: Session, world: dict
) -> None:
    token = _sign_in(client, "member")
    resp = _delete(client, token, password="wrong password")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "PASSWORD_INCORRECT"

    db_session.expire_all()
    member = db_session.get(User, world["member"].id)
    assert member.deleted_at is None
    assert member.email == "member@example.com"
    assert member.failed_login_count == 1
    assert db_session.get(Rack, world["member_rack"].id).deleted_at is None
    # Still signed in.
    assert client.get("/api/community/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_delete_anonymizes_the_user_and_keeps_ledger_and_referral_rows(
    client: TestClient, db_session: Session, world: dict
) -> None:
    member_id = world["member"].id
    old_code = world["member"].referral_code
    token = _sign_in(client, "member")

    resp = _delete(client, token)
    assert resp.status_code == 204

    db_session.expire_all()
    member = db_session.get(User, member_id)
    assert member.deleted_at is not None
    assert member.username.startswith("deleted-") and member.username != "member"
    assert member.email.endswith("@deleted.invalid") and "member" not in member.email
    assert member.display_name is None and member.avatar_url is None and member.bio is None
    assert member.allow_public_avatar is False
    assert member.password_hash == "!account-deleted"
    assert member.referral_code != old_code
    assert member.referred_by == world["referrer"].id

    # Ledger and referral rows stay, still pointing at the same user id.
    assert db_session.query(CanonicalCreditLedgerEntryRecord).filter_by(user_id=member_id).count() == 1
    assert db_session.query(CreditsLedger).filter_by(user_id=member_id).count() == 1
    assert db_session.query(CreditLedgerEntry).filter_by(user_id=member_id).count() == 1
    assert db_session.query(Referral).filter_by(referred_user_id=member_id).count() == 1
    assert db_session.query(AccountReferral).filter_by(referred_user_id=member_id).count() == 1

    # Personal content is removed or detached.
    rack = db_session.get(Rack, world["member_rack"].id)
    assert rack.deleted_at is not None and rack.is_public is False
    assert rack.name == "Deleted rack" and rack.description is None
    image = db_session.get(ImageAssetRecord, world["member_image"].id)
    assert image.deleted_at is not None
    assert not Path(image.storage_path).exists()
    pub = db_session.get(Publication, world["member_pub"].id)
    assert pub.status == "removed" and pub.removed_reason == "ACCOUNT_DELETED"
    assert pub.title == "Removed" and pub.description is None and pub.cover_image_url is None
    assert db_session.query(Comment).filter_by(user_id=member_id).count() == 0
    assert db_session.query(Vote).filter_by(user_id=member_id).count() == 0
    assert db_session.query(PatchUserOverlayRecord).filter_by(user_id=member_id).count() == 0
    assert db_session.query(UserStyleRecipeRecord).filter_by(user_id=member_id).count() == 0
    report = db_session.query(PublicationReport).one()
    assert report.reporter_user_id is None

    # Every session is revoked.
    assert db_session.query(RefreshToken).filter_by(user_id=member_id, revoked_at=None).count() == 0

    # One audit row, with counts and no personal data.
    audit = db_session.query(AdminAuditLog).filter_by(action_type="account_deleted").one()
    assert audit.actor_user_id == member_id and audit.target_id == str(member_id)
    assert audit.delta_json["racks_soft_deleted"] == 1
    assert audit.delta_json["comments_deleted"] == 1
    flat = repr((audit.delta_json, audit.reason, audit.target_id))
    for pii in ("member", "example.com", "Member Rack", "img.example.com"):
        assert pii not in flat


def test_sign_in_and_old_tokens_stop_working_after_delete(
    client: TestClient, db_session: Session, world: dict
) -> None:
    token = _sign_in(client, "member")
    assert _delete(client, token).status_code == 204

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/community/users/me", headers=headers).status_code == 401
    assert client.post(
        "/api/community/auth/login", json={"username": "member", "password": PASSWORD}
    ).status_code == 401
    anonymized = db_session.get(User, world["member"].id).username
    assert client.post(
        "/api/community/auth/login", json={"username": anonymized, "password": PASSWORD}
    ).status_code == 401
    assert client.post("/api/community/auth/refresh", headers={"X-PatchHive-Session": "1"}).status_code == 401
    # A second delete cannot run: the old token is dead.
    assert _delete(client, token).status_code == 401


def test_other_users_are_unaffected(client: TestClient, db_session: Session, world: dict) -> None:
    token = _sign_in(client, "member")
    assert _delete(client, token).status_code == 204

    db_session.expire_all()
    other = db_session.get(User, world["other"].id)
    referrer = db_session.get(User, world["referrer"].id)
    assert other.deleted_at is None and other.email == "other@example.com"
    assert referrer.deleted_at is None and referrer.username == "referrer"
    other_rack = db_session.get(Rack, world["other_rack"].id)
    assert other_rack.deleted_at is None and other_rack.name == "Other Rack"
    other_image = db_session.get(ImageAssetRecord, world["other_image"].id)
    assert other_image.deleted_at is None and Path(other_image.storage_path).exists()
    assert db_session.get(Publication, world["other_pub"].id).status == "published"
    assert db_session.query(Comment).filter_by(user_id=other.id).count() == 1
    assert db_session.query(PatchUserOverlayRecord).filter_by(user_id=other.id).count() == 1
    _sign_in(client, "other")
