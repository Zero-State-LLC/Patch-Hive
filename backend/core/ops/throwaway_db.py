"""Throwaway Postgres targets for runs that truncate tables (the acceptance suite).

The acceptance conftest truncates every public table, so it must never run against a
deployed database. Neon staging and production both name theirs ``patchhive``, so
every helper here refuses that name, and only names matching the throwaway pattern are
ever created or dropped.

Two ways to get a throwaway target on Neon:

- ``database``: ``CREATE DATABASE patchhive_acceptance_<run>_<attempt>`` on the staging
  branch, issued over the staging connection (no row in ``patchhive`` is read or
  written), and ``DROP DATABASE ... WITH (FORCE)`` at the end.
- ``neon-branch``: a child branch of ``staging`` made through the Neon API (needs
  ``NEON_API_KEY``), with a fresh throwaway database on it; the branch is deleted at
  the end, which removes everything on it.

Nothing here logs a URL, host, user or password. Errors carry class names and
SQLSTATE codes only.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

REAL_DATABASE_NAME = "patchhive"
THROWAWAY_PREFIX = "patchhive_acceptance_"
_THROWAWAY_DATABASE = re.compile(r"patchhive_acceptance_[0-9]{1,20}_[0-9]{1,4}")
_THROWAWAY_BRANCH = re.compile(r"acceptance-[0-9]{1,20}-[0-9]{1,4}")
INSUFFICIENT_PRIVILEGE = "42501"

NEON_API = "https://console.neon.tech/api/v2"


class TargetRefused(RuntimeError):
    """The target is a deployed database, or not a name this module may create or drop."""


class ThrowawayError(RuntimeError):
    """Creating, using or removing a throwaway target failed. The message holds no secrets."""


def database_name(url: str) -> str:
    return (make_url(url).database or "").strip()


def refuse_real_database(url: str) -> str:
    """Return the URL's database name, or raise if it is the deployed ``patchhive``."""
    name = database_name(url)
    if not name:
        raise TargetRefused("the database URL names no database")
    if name.lower() == REAL_DATABASE_NAME:
        raise TargetRefused(
            f"refusing database '{REAL_DATABASE_NAME}': that is the deployed database on Neon "
            "staging and production, and this run truncates every table. Use a throwaway database."
        )
    return name


def _require_throwaway_database(name: str) -> str:
    if not _THROWAWAY_DATABASE.fullmatch(name):
        raise TargetRefused(
            f"refusing to create or drop '{name}': not a throwaway acceptance database name"
        )
    return name


def throwaway_database_name(run_id: str, attempt: str) -> str:
    return _require_throwaway_database(f"{THROWAWAY_PREFIX}{run_id}_{attempt}")


def _require_throwaway_branch(name: str) -> str:
    if not _THROWAWAY_BRANCH.fullmatch(name):
        raise TargetRefused(
            f"refusing to create or delete branch '{name}': not a throwaway acceptance branch name"
        )
    return name


def throwaway_branch_name(run_id: str, attempt: str) -> str:
    return _require_throwaway_branch(f"acceptance-{run_id}-{attempt}")


def with_database(url: str, name: str) -> str:
    return make_url(url).set(database=name).render_as_string(hide_password=False)


def _admin_execute(admin_url: str, statement: str, action: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(text(statement))
    except SQLAlchemyError as exc:
        code = getattr(getattr(exc, "orig", None), "pgcode", None)
        hint = ""
        if code == INSUFFICIENT_PRIVILEGE:
            hint = "; the staging role may not create databases, so dispatch with isolation=neon-branch"
        raise ThrowawayError(
            f"{action} failed ({exc.__class__.__name__}, SQLSTATE {code}){hint}"
        ) from None
    finally:
        engine.dispose()


def create_database(admin_url: str, name: str) -> None:
    """Create the throwaway database on the server ``admin_url`` points at."""
    _require_throwaway_database(name)
    _admin_execute(admin_url, f'CREATE DATABASE "{name}"', "CREATE DATABASE")


def drop_database(admin_url: str, name: str) -> None:
    """Drop the throwaway database if it exists, closing any session still on it."""
    _require_throwaway_database(name)
    _admin_execute(admin_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', "DROP DATABASE")


class NeonBranches:
    """The few Neon API v2 calls a child-branch acceptance run needs."""

    def __init__(
        self,
        api_key: str,
        project_id: str,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        locked_wait_seconds: float = 180.0,
    ) -> None:
        if not api_key:
            raise TargetRefused(
                "isolation=neon-branch needs the NEON_API_KEY secret in the staging environment, and it is "
                "not set. Add it, or dispatch with isolation=database."
            )
        if not re.fullmatch(r"[a-z0-9-]{1,64}", project_id or ""):
            raise TargetRefused("NEON_PROJECT_ID is missing or not a Neon project id")
        self._project = project_id
        self._client = client or httpx.Client(base_url=NEON_API, timeout=30.0)
        self._client.headers.update(
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        )
        self._sleep = sleep
        self._locked_wait = locked_wait_seconds

    def _call(
        self, method: str, path: str, *, allow_missing: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        waited = 0.0
        while True:
            response = self._client.request(method, f"/projects/{self._project}{path}", **kwargs)
            # 423: the branch still has operations running (it was just created). Wait and retry.
            if response.status_code == 423 and waited < self._locked_wait:
                self._sleep(5.0)
                waited += 5.0
                continue
            if allow_missing and response.status_code == 404:
                return {}
            if response.status_code >= 400:
                try:
                    detail = str(response.json().get("message", ""))[:200]
                except ValueError:
                    detail = ""
                raise ThrowawayError(
                    f"Neon API {method} {path.split('?')[0]} returned {response.status_code} {detail}".rstrip()
                )
            return response.json() if response.content else {}

    def branch_id(self, name: str) -> str | None:
        branches = self._call("GET", "/branches").get("branches", [])
        matches = [branch["id"] for branch in branches if branch.get("name") == name]
        if len(matches) > 1:
            raise ThrowawayError(f"more than one Neon branch is named '{name}'")
        return matches[0] if matches else None

    def create_branch(self, name: str, parent_name: str) -> str:
        """Create the throwaway child branch of ``parent_name`` with its own compute; return its id."""
        _require_throwaway_branch(name)
        parent_id = self.branch_id(parent_name)
        if parent_id is None:
            raise ThrowawayError(f"no Neon branch is named '{parent_name}'")
        created = self._call(
            "POST",
            "/branches",
            json={
                "branch": {"name": name, "parent_id": parent_id},
                "endpoints": [{"type": "read_write"}],
            },
        )
        return str(created["branch"]["id"])

    def create_database(self, branch_id: str, name: str, owner: str) -> None:
        _require_throwaway_database(name)
        self._call(
            "POST",
            f"/branches/{branch_id}/databases",
            json={"database": {"name": name, "owner_name": owner}},
        )

    def connection_uri(self, branch_id: str, database: str, role: str) -> str:
        found = self._call(
            "GET",
            "/connection_uri",
            params={
                "branch_id": branch_id,
                "database_name": database,
                "role_name": role,
                "pooled": "false",
            },
        )
        uri = str(found.get("uri") or "")
        if not uri:
            raise ThrowawayError("Neon API returned no connection URI for the throwaway database")
        return uri

    def delete_branch(self, name: str) -> bool:
        """Delete the throwaway branch called ``name`` if it exists. Never takes a raw id."""
        _require_throwaway_branch(name)
        branch_id = self.branch_id(name)
        if branch_id is None:
            return False
        self._call("DELETE", f"/branches/{branch_id}", allow_missing=True)
        return True
