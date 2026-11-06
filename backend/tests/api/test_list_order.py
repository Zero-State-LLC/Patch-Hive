"""A paged list needs a fixed order, or a row can repeat across pages while another never appears."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from core.database import get_db
from main import app
from modules.catalog import ModuleCatalog
from modules.models import Module


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def statements(db_session: Session):
    seen: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        seen.append(" ".join(statement.split()))

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", capture)
    yield seen
    event.remove(bind, "before_cursor_execute", capture)


def _page_statement(statements: list[str], table: str) -> str:
    return next(s for s in statements if f"FROM {table}" in s and "LIMIT" in s and "count(" not in s.lower())


def test_the_module_list_pages_by_id(client: TestClient, db_session: Session, statements: list[str]) -> None:
    db_session.add_all(
        Module(brand="Acme", name=f"Row {index}", hp=4, module_type="UTIL", io_ports=[], tags=[], source="test")
        for index in range(5)
    )
    db_session.commit()
    expected = {row.id for row in db_session.query(Module).all()}

    read = [
        row["id"]
        for skip in (0, 2, 4)
        for row in client.get("/api/modules", params={"skip": skip, "limit": 2}).json()["modules"]
    ]

    assert read == sorted(expected)
    assert "ORDER BY modules.id" in _page_statement(statements, "modules")


@pytest.mark.parametrize("sort_order,direction", [("asc", "ASC"), ("desc", "DESC")])
def test_the_catalog_list_breaks_ties_by_id(
    client: TestClient, db_session: Session, statements: list[str], sort_order: str, direction: str
) -> None:
    db_session.add_all(
        ModuleCatalog(
            slug=f"acme-row-{index}", brand="Acme", name=f"Row {index}", is_available="available", source="Manual"
        )
        for index in range(5)
    )
    db_session.commit()

    read = [
        row["slug"]
        for skip in (0, 2, 4)
        for row in client.get(
            "/api/modules/catalog", params={"skip": skip, "limit": 2, "sort_by": "brand", "sort_order": sort_order}
        ).json()["modules"]
    ]

    assert sorted(read) == [f"acme-row-{index}" for index in range(5)]
    assert f"ORDER BY module_catalog.brand {direction}, module_catalog.id" in _page_statement(
        statements, "module_catalog"
    )


def test_the_rack_list_pages_by_id(client: TestClient, statements: list[str]) -> None:
    assert client.get("/api/racks", params={"limit": 2}).status_code == 200
    assert "ORDER BY racks.id" in _page_statement(statements, "racks")
