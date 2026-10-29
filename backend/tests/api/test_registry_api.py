"""API tests for Product Database registry endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate
from community.auth import require_auth
from core.database import get_db
from main import app
from modules.catalog import ModuleCatalog
from registry.models import DeviceModel, Manufacturer


@pytest.fixture
def client(db_session: Session):
    manufacturer = Manufacturer(
        slug="test-instruments",
        canonical_name="Test Instruments",
        status="active",
        provenance={"source": "test"},
    )
    db_session.add(manufacturer)
    db_session.flush()
    db_session.add(
        DeviceModel(
            manufacturer_id=manufacturer.id,
            slug="math-test",
            canonical_name="Math Test",
            device_type="module",
            format="eurorack",
            hp=12,
            provenance={"source": "test"},
        )
    )
    db_session.add_all(
        [
            # Matched to Test Instruments by brand name (case-insensitive) and by alias.
            ModuleCatalog(slug="test-instruments-maths-osc", brand="test instruments", name="Maths Osc", hp=10, category="VCO"),
            ModuleCatalog(slug="test-instruments-filter", brand="TI", name="Filter 100%", hp=None, category="VCF"),
            # Another maker's row: never counted for Test Instruments.
            ModuleCatalog(slug="other-maker-delay", brand="Other Maker", name="Delay", hp=8, category="FX"),
        ]
    )
    manufacturer.aliases = ["TI"]
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_registry_manufacturers_endpoint(client: TestClient):
    response = client.get("/api/registry/manufacturers?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"] == [
        {
            "id": data["items"][0]["id"],
            "slug": "test-instruments",
            "name": "Test Instruments",
            "model_count": 3,
            "status": "active",
        }
    ]


def test_registry_search_endpoint(client: TestClient):
    response = client.get("/api/registry/search?q=maths&limit=3")
    assert response.status_code == 200
    results = response.json()["results"]
    assert [(r["brand"], r["name"], r["hp"]) for r in results] == [("test instruments", "Maths Osc", 10)]


def test_registry_search_reads_registry_models_then_the_module_catalog(client: TestClient):
    response = client.get("/api/registry/search?q=&limit=10")
    names = [r["name"] for r in response.json()["results"]]
    assert names[0] == "Math Test"  # registry device model first
    assert set(names[1:]) == {"Maths Osc", "Filter 100%", "Delay"}


def test_registry_search_escapes_like_wildcards(client: TestClient):
    response = client.get("/api/registry/search", params={"q": "100%"})
    assert [r["name"] for r in response.json()["results"]] == ["Filter 100%"]
    response = client.get("/api/registry/search", params={"q": "_"})
    assert response.json()["results"] == []


def test_registry_search_filters_by_brand_slug(client: TestClient):
    response = client.get("/api/registry/search", params={"brand": "test-instruments", "limit": 10})
    names = {r["name"] for r in response.json()["results"]}
    assert names == {"Math Test", "Maths Osc", "Filter 100%"}


def test_registry_manufacturer_models_include_catalog_rows(client: TestClient):
    detail = client.get("/api/registry/manufacturers/test-instruments").json()
    assert detail["model_count"] == 3
    assert {m["name"] for m in detail["models"]} == {"Math Test", "Maths Osc", "Filter 100%"}
    models = client.get("/api/registry/manufacturers/test-instruments/models").json()["models"]
    assert [m["name"] for m in models] == ["Math Test", "Filter 100%", "Maths Osc"]


def test_registry_coverage_endpoint(client: TestClient):
    response = client.get("/api/registry/coverage")
    assert response.status_code == 200
    assert response.json() == {
        "total_manufacturers": 1,
        "total_models": 4,
        "hp_coverage_pct": 75.0,
    }


def test_registry_admin_create_requires_authentication(client: TestClient):
    response = client.post(
        "/api/registry/admin/manufacturers",
        json={"slug": "new-brand", "canonical_name": "New Brand"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_registry_admin_create_rejects_non_admin_role(client: TestClient):
    class CommunityUser:
        role = "User"

    app.dependency_overrides[require_auth] = lambda: CommunityUser()
    try:
        response = client.post(
            "/api/registry/admin/manufacturers",
            json={"slug": "new-brand", "canonical_name": "New Brand"},
        )
    finally:
        app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin mutation access required"}


def test_registry_admin_can_create_manufacturer(client: TestClient):
    app.dependency_overrides[require_admin_mutate] = lambda: object()
    payload = {
        "slug": "new-brand",
        "canonical_name": "New Brand",
        "aliases": ["NewBrand"],
    }
    try:
        response = client.post("/api/registry/admin/manufacturers", json=payload)
        duplicate = client.post("/api/registry/admin/manufacturers", json=payload)
    finally:
        app.dependency_overrides.pop(require_admin_mutate, None)

    assert response.status_code == 200
    assert response.json()["slug"] == "new-brand"
    assert duplicate.status_code == 400
    assert duplicate.json() == {"detail": "Slug already exists"}
