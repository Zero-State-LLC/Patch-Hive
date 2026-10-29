"""
API tests for publishing endpoints.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from community.models import User
from core import create_access_token, get_db
from main import app
from patches.models import Patch
from publishing.models import Export, Publication
from racks.models import Rack


@pytest.fixture
def client(db_session: Session):
    """Create a test client with database override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth_headers(user: User) -> dict:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def _create_patch(db_session: Session, rack: Rack) -> Patch:
    patch = Patch(
        rack_id=rack.id,
        name="Test Patch",
        category="Voice",
        connections=[],
        generation_seed=123,
        generation_version="1.0",
    )
    db_session.add(patch)
    db_session.commit()
    db_session.refresh(patch)
    return patch


def _create_export(
    db_session: Session, owner: User, patch: Patch | None, rack: Rack | None
) -> Export:
    export = Export(
        owner_user_id=owner.id,
        patch_id=patch.id if patch else None,
        rack_id=rack.id if rack else None,
        export_type="patch" if patch else "rack",
        license="CC BY-NC 4.0",
        run_id="run-123",
        generated_at=datetime.utcnow(),
        patch_count=1,
        manifest_hash="hash-123",
        artifact_urls={
            "pdf": "/tmp/example.pdf",
            "svg": "/tmp/example.svg",
            "zip": "/tmp/example.zip",
        },
    )
    db_session.add(export)
    db_session.commit()
    db_session.refresh(export)
    return export


def _create_publication(db_session: Session, export: Export, owner: User, **kwargs) -> Publication:
    publication = Publication(
        export_id=export.id,
        publisher_user_id=owner.id,
        slug=kwargs.get("slug", f"pub-{export.id}"),
        visibility=kwargs.get("visibility", "public"),
        status=kwargs.get("status", "published"),
        allow_download=kwargs.get("allow_download", True),
        allow_remix=kwargs.get("allow_remix", False),
        title=kwargs.get("title", "Test Publication"),
        description=kwargs.get("description", "Test description"),
        cover_image_url=None,
        published_at=datetime.utcnow(),
    )
    db_session.add(publication)
    db_session.commit()
    db_session.refresh(publication)
    return publication


class TestPublishingAPI:
    """Tests for publishing endpoints."""

    def test_cannot_publish_export_not_owned(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        owner = sample_user
        other = User(username="other", email="other@example.com", password_hash="hash")
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        rack = Rack(user_id=owner.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        patch = _create_patch(db_session, rack)
        export = _create_export(db_session, owner, patch, None)

        payload = {
            "export_id": export.id,
            "title": "Unauthorized",
            "visibility": "public",
            "allow_download": True,
            "allow_remix": False,
        }
        response = client.post(
            "/api/me/publications",
            json=payload,
            headers=_auth_headers(other),
        )

        assert response.status_code == 403

    def test_unlisted_not_in_gallery(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        patch = _create_patch(db_session, rack)
        export = _create_export(db_session, sample_user, patch, None)
        _create_publication(db_session, export, sample_user, visibility="unlisted")

        response = client.get("/api/gallery/publications")
        assert response.status_code == 200
        data = response.json()
        assert data["publications"] == []

    def test_removed_publication_not_accessible(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        patch = _create_patch(db_session, rack)
        export = _create_export(db_session, sample_user, patch, None)
        publication = _create_publication(db_session, export, sample_user, status="removed")

        response = client.get(f"/api/p/{publication.slug}")
        assert response.status_code == 404

    def test_public_page_never_exposes_private_fields(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        sample_user.email = "private@example.com"
        db_session.commit()

        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        patch = _create_patch(db_session, rack)
        export = _create_export(db_session, sample_user, patch, None)
        publication = _create_publication(db_session, export, sample_user)

        response = client.get(f"/api/p/{publication.slug}")
        assert response.status_code == 200
        data = response.json()
        assert "email" not in response.text
        assert "user_id" not in response.text
        assert "publisher_user_id" not in response.text
        assert data["publisher_display"] == "PatchHive User"

    def test_allow_download_gating(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        patch = _create_patch(db_session, rack)
        export = _create_export(db_session, sample_user, patch, None)
        publication = _create_publication(
            db_session,
            export,
            sample_user,
            allow_download=False,
        )

        response = client.get(f"/api/p/{publication.slug}")
        assert response.status_code == 200
        assert response.json()["download_urls"] is None

        download_response = client.get(f"/api/p/{publication.slug}/download/pdf")
        assert download_response.status_code == 403

    def test_admin_moderation_audited(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash="hash",
            is_admin=True,
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)

        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        patch = _create_patch(db_session, rack)
        export = _create_export(db_session, sample_user, patch, None)
        publication = _create_publication(db_session, export, sample_user)

        response = client.post(
            f"/api/admin/publications/{publication.id}/hide",
            json={"reason": "Policy breach"},
            headers=_auth_headers(admin),
        )

        assert response.status_code == 200
        db_session.refresh(publication)
        assert publication.status == "hidden"
        assert publication.moderation_audit_id is not None

        audit = (
            db_session.query(AdminAuditLog)
            .filter(AdminAuditLog.id == publication.moderation_audit_id)
            .first()
        )
        assert audit is not None
        assert audit.action_type == "hide_publication"

    def test_owner_cannot_lift_moderation(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        patch = _create_patch(db_session, rack)
        owner = _auth_headers(sample_user)

        # The owner's own hide can be undone.
        own = _create_publication(db_session, _create_export(db_session, sample_user, patch, None), sample_user)
        url = f"/api/me/publications/{own.id}"
        assert client.patch(url, json={"status": "hidden"}, headers=owner).status_code == 200
        assert client.patch(url, json={"status": "published"}, headers=owner).status_code == 200

        # A removed publication, or one an admin hid, stays where moderation put it.
        removed = _create_publication(
            db_session, _create_export(db_session, sample_user, patch, None), sample_user,
            slug="removed-pub", status="removed",
        )
        hidden = _create_publication(
            db_session, _create_export(db_session, sample_user, patch, None), sample_user,
            slug="hidden-pub", status="hidden",
        )
        audit = AdminAuditLog(
            actor_user_id=sample_user.id, actor_role="Admin", action_type="hide_publication",
            target_type="publication", target_id=str(hidden.id),
        )
        db_session.add(audit)
        db_session.flush()
        hidden.moderation_audit_id = audit.id
        db_session.commit()
        for pub in (removed, hidden):
            resp = client.patch(
                f"/api/me/publications/{pub.id}", json={"status": "published"}, headers=owner
            )
            assert resp.status_code == 409
            db_session.refresh(pub)
            assert pub.status in {"removed", "hidden"}

    def test_a_removed_publication_cannot_be_edited(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        from tests.conftest import bearer_headers

        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        patch = _create_patch(db_session, rack)
        removed = _create_publication(
            db_session, _create_export(db_session, sample_user, patch, None), sample_user,
            slug="removed-edit", status="removed",
        )
        before = removed.title
        resp = client.patch(
            f"/api/me/publications/{removed.id}",
            json={"title": "Back again", "visibility": "public"},
            headers=bearer_headers(sample_user),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "PUBLICATION_UNDER_MODERATION"
        db_session.refresh(removed)
        assert removed.title == before and removed.status == "removed"

    def test_a_deleted_rack_cannot_be_exported(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        patch = _create_patch(db_session, rack)
        rack.deleted_at = datetime.utcnow()
        db_session.commit()
        owner = _auth_headers(sample_user)
        for source in ({"source_type": "rack", "source_id": rack.id}, {"source_type": "patch", "source_id": patch.id}):
            resp = client.post("/api/me/exports", json=source, headers=owner)
            assert resp.status_code == 404, resp.text

    def test_publication_lifecycle_follows_the_spec(
        self, client: TestClient, db_session: Session, sample_user: User, sample_case
    ):
        """Spec 002: create -> draft; owner publishes; unlisted pairs are 409 and change nothing."""
        rack = Rack(user_id=sample_user.id, name="Rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.commit()
        export = _create_export(db_session, sample_user, _create_patch(db_session, rack), None)
        owner = _auth_headers(sample_user)
        created = client.post(
            "/api/me/publications",
            json={"export_id": export.id, "title": "Mine", "visibility": "public",
                  "allow_download": True, "allow_remix": False},
            headers=owner,
        )
        assert created.status_code == 201, created.text
        pub = created.json()
        assert pub["status"] == "draft"
        assert client.get(f"/api/p/{pub['slug']}").status_code == 404  # drafts are not public
        url = f"/api/me/publications/{pub['id']}"
        assert client.patch(url, json={"status": "hidden"}, headers=owner).status_code == 409
        assert client.patch(url, json={"status": "published"}, headers=owner).json()["status"] == "published"

        admin = User(username="mod", email="mod@example.com", password_hash="h", is_admin=True)
        db_session.add(admin)
        db_session.commit()
        mod = _auth_headers(admin)
        reason = {"reason": "Policy"}
        assert client.post(f"/api/admin/publications/{pub['id']}/hide", json=reason, headers=mod).status_code == 200
        # Already hidden: hiding again is not a listed transition; reports need a published page.
        assert client.post(f"/api/admin/publications/{pub['id']}/hide", json=reason, headers=mod).status_code == 409
        assert client.post(f"/api/p/{pub['slug']}/report", json={"reason": "spam"}).status_code == 404
        assert client.post(f"/api/admin/publications/{pub['id']}/remove", json=reason, headers=mod).status_code == 200
        assert client.post(f"/api/admin/publications/{pub['id']}/remove", json=reason, headers=mod).status_code == 409
