"""Spec 004 T050 over HTTP: a STUDIO subscriber exports without credits, with the tier
from the subscription, until the period's fair-use cap answers 429
``FAIR_USE_CAP_REACHED`` (FR-004, OQ-8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.models import CanonicalExportRecord
from tests.api.test_canon_export_api import _auth_headers, client  # noqa: F401 (fixture)
from tests.unit.test_canon_contracts import _persist_hierarchy
from tests.unit.test_commerce_tier_entitlements import _studio_grant, _subscription


def _body(key: str) -> dict[str, str]:
    return {
        "source_run_id": "run-1",
        "source_rig_revision_id": "rig-rev-1",
        "artifact_manifest_hash": "a" * 64,
        "idempotency_key": key,
    }


def test_a_studio_subscriber_exports_without_credits_until_the_cap(
    export_fulfillment_pending, client: TestClient, db_session: Session  # noqa: F811
) -> None:
    user, _patch = _persist_hierarchy(db_session)
    now = datetime.now(timezone.utc)
    record = _subscription(db_session, user, created_at=now - timedelta(days=1))
    _studio_grant(
        db_session, record, cap=1, start=now - timedelta(days=1), end=now + timedelta(days=29)
    )

    first = client.post("/api/canon/exports", headers=_auth_headers(user), json=_body("studio-a"))
    assert first.status_code == 201, first.text
    assert (first.json()["credit_cost"], first.json()["ledger_entry_id"]) == (0, None)
    export = db_session.get(CanonicalExportRecord, first.json()["export_id"])
    assert export.resolved_tier == "studio"

    capped = client.post("/api/canon/exports", headers=_auth_headers(user), json=_body("studio-b"))
    assert capped.status_code == 429
    assert capped.json()["detail"] == "FAIR_USE_CAP_REACHED"
    assert db_session.query(CanonicalExportRecord).count() == 1
