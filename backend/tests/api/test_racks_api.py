"""
API endpoint tests for /api/racks.
Tests the Rack CRUD endpoints using FastAPI TestClient.
"""

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from community.models import User
from main import app
from modules.models import Module
from racks.models import Rack, RackModule


@pytest.fixture
def client(db_session: Session, owner_headers: dict):
    """Test client signed in as the owner of the sample racks."""
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers=owner_headers)
    app.dependency_overrides.clear()


class TestRacksAPI:
    """Tests for /api/racks endpoints."""

    def test_create_rack_minimal(self, client: TestClient, sample_case: Case, sample_vco: Module):
        """Test creating a minimal rack with one module."""
        payload = {
            "case_id": sample_case.id,
            "modules": [{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0}],
        }

        response = client.post("/api/racks", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["case_id"] == sample_case.id
        assert data["name"] is not None  # Auto-generated
        assert len(data["modules"]) == 1
        assert data["modules"][0]["module_id"] == sample_vco.id
        assert data["vote_count"] == 0

    def test_create_rack_with_name(self, client: TestClient, sample_case: Case, sample_vco: Module):
        """Test creating a rack with custom name."""
        payload = {
            "case_id": sample_case.id,
            "name": "My Custom Rack",
            "description": "Test rack description",
            "tags": ["ambient", "generative"],
            "is_public": True,
            "modules": [{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0}],
        }

        response = client.post("/api/racks", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Custom Rack"
        assert data["description"] == "Test rack description"
        assert data["tags"] == ["ambient", "generative"]
        assert data["is_public"] is True

    def test_create_rack_with_multiple_modules(
        self,
        client: TestClient,
        sample_case: Case,
        sample_vco: Module,
        sample_vcf: Module,
        sample_vca: Module,
    ):
        """Test creating a rack with multiple modules."""
        payload = {
            "case_id": sample_case.id,
            "modules": [
                {"module_id": sample_vco.id, "row_index": 0, "start_hp": 0},
                {"module_id": sample_vcf.id, "row_index": 0, "start_hp": 10},
                {"module_id": sample_vca.id, "row_index": 0, "start_hp": 18},
            ],
        }

        response = client.post("/api/racks", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert len(data["modules"]) == 3
        # Verify module order and positions
        assert data["modules"][0]["start_hp"] == 0
        assert data["modules"][1]["start_hp"] == 10
        assert data["modules"][2]["start_hp"] == 18

    def test_create_rack_invalid_case(self, client: TestClient, sample_vco: Module):
        """Test creating rack with non-existent case returns serializable 400."""
        payload = {
            "case_id": 99999,  # Non-existent
            "modules": [{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0}],
        }

        response = client.post("/api/racks", json=payload)

        assert response.status_code == 400
        body = response.json()
        detail = body.get("detail") or body
        assert detail.get("message") == "Rack validation failed"
        assert isinstance(detail.get("errors"), list)
        assert detail["errors"][0]["field"] == "case_id"

    def test_create_rack_overlapping_modules(
        self, client: TestClient, sample_case: Case, sample_vco: Module
    ):
        """Test that overlapping modules are rejected with serializable 400."""
        payload = {
            "case_id": sample_case.id,
            "modules": [
                {"module_id": sample_vco.id, "row_index": 0, "start_hp": 0},
                {"module_id": sample_vco.id, "row_index": 0, "start_hp": 5},  # Overlaps!
            ],
        }

        response = client.post("/api/racks", json=payload)

        assert response.status_code == 400
        detail = response.json().get("detail") or response.json()
        assert detail.get("message") == "Rack validation failed"
        assert any("overlap" in (e.get("message") or "").lower() for e in detail.get("errors", []))

    def test_list_racks_empty(self, client: TestClient):
        """Test listing racks when none exist."""
        response = client.get("/api/racks")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["racks"] == []

    def test_list_racks(self, client: TestClient, sample_rack_basic: Rack, sample_rack_full: Rack):
        """Test listing multiple racks."""
        response = client.get("/api/racks")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["racks"]) == 2

    def test_list_racks_pagination(
        self, client: TestClient, sample_rack_basic: Rack, sample_rack_full: Rack
    ):
        """Test rack list pagination."""
        # Get first rack only
        response = client.get("/api/racks?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["racks"]) == 1

        # Get second rack with offset
        response = client.get("/api/racks?skip=1&limit=1")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["racks"]) == 1

    def test_list_racks_filter_public(
        self, client: TestClient, db_session: Session, sample_rack_basic: Rack
    ):
        """Test filtering racks by is_public."""
        # Make one rack public
        sample_rack_basic.is_public = True
        db_session.commit()

        # Filter for public racks
        response = client.get("/api/racks?is_public=true")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert all(rack["is_public"] for rack in data["racks"])

    def test_get_rack(self, client: TestClient, sample_rack_basic: Rack):
        """Test getting a specific rack by ID."""
        response = client.get(f"/api/racks/{sample_rack_basic.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_rack_basic.id
        assert data["name"] == sample_rack_basic.name
        assert "modules" in data
        assert "case" in data
        assert data["vote_count"] == 0

    def test_get_rack_not_found(self, client: TestClient):
        """Test getting non-existent rack returns 404."""
        response = client.get("/api/racks/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_rack_name(
        self, client: TestClient, db_session: Session, sample_rack_basic: Rack
    ):
        """Test updating rack name."""
        payload = {"name": "Updated Rack Name"}

        response = client.patch(f"/api/racks/{sample_rack_basic.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Rack Name"

        # Verify in database
        db_session.refresh(sample_rack_basic)
        assert sample_rack_basic.name == "Updated Rack Name"

    def test_update_rack_description(self, client: TestClient, sample_rack_basic: Rack):
        """Test updating rack description."""
        payload = {"description": "New description"}

        response = client.patch(f"/api/racks/{sample_rack_basic.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "New description"

    def test_update_rack_tags(self, client: TestClient, sample_rack_basic: Rack):
        """Test updating rack tags."""
        payload = {"tags": ["techno", "acid"]}

        response = client.patch(f"/api/racks/{sample_rack_basic.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == ["techno", "acid"]

    def test_update_rack_public(self, client: TestClient, sample_rack_basic: Rack):
        """Test toggling rack public status."""
        payload = {"is_public": True}

        response = client.patch(f"/api/racks/{sample_rack_basic.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["is_public"] is True

    def test_update_rack_modules(
        self,
        client: TestClient,
        db_session: Session,
        sample_rack_basic: Rack,
        sample_lfo: Module,
    ):
        """Test updating rack module configuration."""
        # Add LFO to rack
        payload = {"modules": [{"module_id": sample_lfo.id, "row_index": 0, "start_hp": 0}]}

        response = client.patch(f"/api/racks/{sample_rack_basic.id}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["modules"]) == 1
        assert data["modules"][0]["module_id"] == sample_lfo.id

        # Verify old modules were removed
        old_modules = (
            db_session.query(RackModule).filter(RackModule.rack_id == sample_rack_basic.id).all()
        )
        assert len(old_modules) == 1
        assert old_modules[0].module_id == sample_lfo.id

    def test_update_rack_not_found(self, client: TestClient):
        """Test updating non-existent rack returns 404."""
        payload = {"name": "Updated Name"}

        response = client.patch("/api/racks/99999", json=payload)

        assert response.status_code == 404

    def test_delete_rack(self, client: TestClient, db_session: Session, sample_rack_basic: Rack):
        """Test deleting a rack."""
        rack_id = sample_rack_basic.id

        response = client.delete(f"/api/racks/{rack_id}")

        assert response.status_code == 204

        # Verify rack is deleted
        deleted_rack = db_session.query(Rack).filter(Rack.id == rack_id).first()
        assert deleted_rack is None

        # Verify associated modules are also deleted (cascade)
        remaining_modules = db_session.query(RackModule).filter(RackModule.rack_id == rack_id).all()
        assert len(remaining_modules) == 0

    def test_delete_rack_not_found(self, client: TestClient):
        """Test deleting non-existent rack returns 404."""
        response = client.delete("/api/racks/99999")

        assert response.status_code == 404


class TestHealthEndpoint:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Liveness probe — process up, no DB requirement."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data
        assert "abx_core_version" in data

    def test_health_ready(self, client: TestClient):
        """Readiness probe — includes database connectivity."""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "ok"
        assert "app" in data


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "version" in data
        assert data["docs_url"] == "/docs"
        assert "abx_core_version" in data
