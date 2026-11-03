"""Throwaway acceptance targets: never the deployed `patchhive`, only names this code made."""

from __future__ import annotations

import json
import os

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from core.ops import throwaway_db
from core.ops.throwaway_db import (
    NeonBranches,
    TargetRefused,
    ThrowawayError,
    create_database,
    drop_database,
    refuse_real_database,
    throwaway_branch_name,
    throwaway_database_name,
    with_database,
)

NEON_URL = "postgresql://owner:s3cret-pw@ep-cool-name-123.us-west-2.aws.neon.tech/patchhive?sslmode=require"
# The CI service Postgres (same as tests/test_catalog_population.py); skipped when absent.
ADMIN_URL = os.environ.get("THROWAWAY_ADMIN_URL", "postgresql://patchhive:patchhive_test@127.0.0.1:5432/postgres")


@pytest.mark.parametrize(
    "url",
    [
        NEON_URL,
        "postgresql://u:p@localhost:5432/PATCHHIVE",
        "postgresql+psycopg2://u:p@db/patchhive",
    ],
)
def test_the_deployed_database_name_is_refused(url: str) -> None:
    with pytest.raises(TargetRefused, match="refusing database 'patchhive'"):
        refuse_real_database(url)


def test_a_url_without_a_database_is_refused() -> None:
    with pytest.raises(TargetRefused, match="names no database"):
        refuse_real_database("postgresql://u:p@localhost:5432")


@pytest.mark.parametrize("name", ["patchhive_test", "patchhive_acceptance", "patchhive_acceptance_42_1"])
def test_other_databases_are_allowed(name: str) -> None:
    assert refuse_real_database(f"postgresql://u:p@localhost/{name}") == name


def test_throwaway_names_come_from_run_id_and_attempt() -> None:
    assert throwaway_database_name("123456", "2") == "patchhive_acceptance_123456_2"
    assert throwaway_branch_name("123456", "2") == "acceptance-123456-2"


@pytest.mark.parametrize(("run_id", "attempt"), [("", "1"), ("1", ""), ("1;drop", "1"), ("abc", "1"), ("1", "1 2")])
def test_throwaway_names_need_digits(run_id: str, attempt: str) -> None:
    with pytest.raises(TargetRefused):
        throwaway_database_name(run_id, attempt)
    with pytest.raises(TargetRefused):
        throwaway_branch_name(run_id, attempt)


@pytest.mark.parametrize("name", ["patchhive", "postgres", "patchhive_test", 'x"; DROP DATABASE patchhive; --'])
def test_create_and_drop_refuse_other_names_before_connecting(name: str) -> None:
    unreachable = "postgresql://u:p@unreachable.invalid:1/postgres"
    with pytest.raises(TargetRefused, match="not a throwaway"):
        create_database(unreachable, name)
    with pytest.raises(TargetRefused, match="not a throwaway"):
        drop_database(unreachable, name)


def test_with_database_keeps_credentials_and_query() -> None:
    target = with_database(NEON_URL, "patchhive_acceptance_1_1")
    assert target.endswith("/patchhive_acceptance_1_1?sslmode=require")
    assert "s3cret-pw" in target


def test_connection_errors_name_the_class_not_the_host() -> None:
    with pytest.raises(ThrowawayError) as caught:
        create_database("postgresql://owner:pw@127.0.0.1:1/postgres", "patchhive_acceptance_1_1")
    message = str(caught.value)
    assert message.startswith("CREATE DATABASE failed (OperationalError")
    assert "127.0.0.1" not in message and "owner" not in message and "pw" not in message


# Neon API --------------------------------------------------------------------------------


class FakeNeon:
    """A Neon API stand-in: one `staging` branch, records every request."""

    def __init__(self, locked: int = 0) -> None:
        self.requests: list[httpx.Request] = []
        self.branches = [{"id": "br-staging", "name": "staging"}, {"id": "br-main", "name": "main"}]
        self.locked = locked

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/api/v2/projects/polished-night-86976142")
        if request.method == "POST" and self.locked:
            self.locked -= 1
            return httpx.Response(423, json={"message": "project already has running operations"})
        if request.method == "GET" and path == "/branches":
            return httpx.Response(200, json={"branches": self.branches})
        if request.method == "POST" and path == "/branches":
            body = json.loads(request.content)
            self.branches.append({"id": "br-child", "name": body["branch"]["name"]})
            return httpx.Response(201, json={"branch": {"id": "br-child", "name": body["branch"]["name"]}})
        if request.method == "POST" and path == "/branches/br-child/databases":
            return httpx.Response(201, json={"database": json.loads(request.content)["database"]})
        if request.method == "GET" and path == "/connection_uri":
            params = request.url.params
            uri = f"postgresql://{params['role_name']}:pw@ep-child.neon.tech/{params['database_name']}?sslmode=require"
            return httpx.Response(200, json={"uri": uri})
        if request.method == "DELETE" and path == "/branches/br-child":
            self.branches = [branch for branch in self.branches if branch["id"] != "br-child"]
            return httpx.Response(200, json={"branch": {"id": "br-child"}})
        return httpx.Response(404, json={"message": "not found"})


def _neon(fake: FakeNeon, sleeps: list[float] | None = None) -> NeonBranches:
    client = httpx.Client(base_url=throwaway_db.NEON_API, transport=httpx.MockTransport(fake))
    return NeonBranches(
        "neon-key-123",
        "polished-night-86976142",
        client=client,
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
    )


def test_neon_branch_isolation_refuses_without_an_api_key() -> None:
    with pytest.raises(TargetRefused, match="NEON_API_KEY .* not set.*isolation=database"):
        NeonBranches("", "polished-night-86976142")


def test_neon_branch_lifecycle() -> None:
    fake = FakeNeon()
    neon = _neon(fake)

    branch_id = neon.create_branch("acceptance-77-1", "staging")
    neon.create_database(branch_id, "patchhive_acceptance_77_1", "owner")
    uri = neon.connection_uri(branch_id, "patchhive_acceptance_77_1", "owner")
    deleted = neon.delete_branch("acceptance-77-1")

    assert branch_id == "br-child" and deleted is True
    assert refuse_real_database(uri) == "patchhive_acceptance_77_1"
    create = next(r for r in fake.requests if r.method == "POST" and r.url.path.endswith("/branches"))
    assert json.loads(create.content) == {
        "branch": {"name": "acceptance-77-1", "parent_id": "br-staging"},
        "endpoints": [{"type": "read_write"}],
    }
    database = next(r for r in fake.requests if r.url.path.endswith("/databases"))
    assert json.loads(database.content) == {"database": {"name": "patchhive_acceptance_77_1", "owner_name": "owner"}}
    lookup = next(r for r in fake.requests if r.url.path.endswith("/connection_uri"))
    assert lookup.url.params["pooled"] == "false" and lookup.url.params["branch_id"] == "br-child"
    assert all(r.headers["Authorization"] == "Bearer neon-key-123" for r in fake.requests)
    assert [r.method for r in fake.requests if r.method == "DELETE"] == ["DELETE"]


def test_neon_waits_while_the_new_branch_is_locked() -> None:
    sleeps: list[float] = []
    neon = _neon(FakeNeon(locked=2), sleeps)
    assert neon.create_branch("acceptance-77-1", "staging") == "br-child"
    assert sleeps == [5.0, 5.0]


def test_neon_never_creates_or_deletes_a_non_throwaway_branch() -> None:
    fake = FakeNeon()
    neon = _neon(fake)
    for name in ("staging", "main", "acceptance-x-1"):
        with pytest.raises(TargetRefused):
            neon.delete_branch(name)
        with pytest.raises(TargetRefused):
            neon.create_branch(name, "staging")
    with pytest.raises(TargetRefused):
        neon.create_database("br-staging", "patchhive", "owner")
    assert fake.requests == []


def test_neon_delete_of_a_missing_branch_is_a_no_op() -> None:
    fake = FakeNeon()
    assert _neon(fake).delete_branch("acceptance-77-1") is False
    assert [r.method for r in fake.requests] == ["GET"]


def test_neon_errors_carry_status_and_message_but_not_the_key() -> None:
    neon = _neon(FakeNeon())
    with pytest.raises(ThrowawayError, match="no Neon branch is named 'nope'"):
        neon.create_branch("acceptance-77-1", "nope")
    with pytest.raises(ThrowawayError) as caught:
        neon.create_database("br-unknown", "patchhive_acceptance_77_1", "owner")
    assert "returned 404 not found" in str(caught.value)
    assert "neon-key-123" not in str(caught.value)


# Real Postgres (CI service container) ----------------------------------------------------


def _admin_or_skip() -> None:
    engine = create_engine(ADMIN_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        pytest.skip(f"throwaway postgres is unavailable ({exc.__class__.__name__})")
    finally:
        engine.dispose()


def _exists(name: str) -> bool:
    engine = create_engine(ADMIN_URL)
    try:
        with engine.connect() as conn:
            return bool(conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar())
    finally:
        engine.dispose()


def test_create_then_drop_on_postgres_even_with_a_session_open() -> None:
    _admin_or_skip()
    name = "patchhive_acceptance_999999_1"
    drop_database(ADMIN_URL, name)
    create_database(ADMIN_URL, name)
    assert _exists(name)
    holder = create_engine(with_database(ADMIN_URL, name))
    connection = holder.connect()
    try:
        drop_database(ADMIN_URL, name)  # WITH (FORCE) closes the open session
    finally:
        try:
            connection.close()
        except SQLAlchemyError:
            pass
        holder.dispose()
    assert not _exists(name)
    drop_database(ADMIN_URL, name)  # idempotent
