"""Acceptance: credits + exports via the canonical ledger boundary.

MVP debit path is POST /api/canon/exports. Admin grants dual-write the
canonical ledger so grant → export works end-to-end without the legacy
POST /api/export/runs/{id}/patchbook debit route.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from canon.exports import compensate_failed_export, credit_balance
from canon.models import CanonicalCreditLedgerEntryRecord, CanonicalExportRecord
from core import settings
from runs.bridge import (
    ensure_legacy_run_export_bridge,
)
from runs.models import Run


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _attach_canon_export_sources(db_session: Session, *, run_id: int) -> dict[str, str]:
    """Ensure server bridge hierarchy for a golden-demo legacy run."""
    run = db_session.get(Run, run_id)
    assert run is not None
    bridge = ensure_legacy_run_export_bridge(db_session, run)
    db_session.commit()
    assert bridge.export_bridge_ready
    return bridge.as_export_body_fields()


def _canon_export_body(sources: dict[str, str], idempotency_key: str) -> dict:
    return {
        "source_run_id": sources["source_run_id"],
        "source_rig_revision_id": sources["source_rig_revision_id"],
        "artifact_manifest_hash": sources["artifact_manifest_hash"],
        "formats": ["pdf", "json"],
        "license": "personal",
        "idempotency_key": idempotency_key,
    }


def test_export_blocked_without_credits(export_fulfillment_pending, api_client, db_session: Session, golden_demo_seed):
    sources = _attach_canon_export_sources(db_session, run_id=golden_demo_seed.run_id)

    login_resp = api_client.post(
        "/api/community/auth/login",
        json={"username": golden_demo_seed.username, "password": golden_demo_seed.password},
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]

    resp = api_client.post(
        "/api/canon/exports",
        headers=_auth_headers(token),
        json=_canon_export_body(sources, "acceptance-no-credits-1"),
    )
    assert resp.status_code == 402
    assert resp.json()["detail"] == "INSUFFICIENT_CREDITS"

    assert credit_balance(db_session, golden_demo_seed.user_id) == 0
    ledger_entries = (
        db_session.query(CanonicalCreditLedgerEntryRecord)
        .filter(CanonicalCreditLedgerEntryRecord.user_id == golden_demo_seed.user_id)
        .all()
    )
    exports = (
        db_session.query(CanonicalExportRecord)
        .filter(CanonicalExportRecord.user_id == golden_demo_seed.user_id)
        .all()
    )
    assert not ledger_entries
    assert not exports


def test_admin_grant_then_export_succeeds(export_fulfillment_pending, 
    api_client, db_session: Session, golden_demo_seed, admin_user
):
    sources = _attach_canon_export_sources(db_session, run_id=golden_demo_seed.run_id)

    admin_login = api_client.post(
        "/api/community/auth/login",
        json={"username": admin_user.username, "password": "admin-pass"},
    )
    admin_login.raise_for_status()
    admin_token = admin_login.json()["access_token"]

    grant = api_client.post(
        f"/api/admin/users/{golden_demo_seed.user_id}/credits/grant",
        json={"credits": 10, "reason": "acceptance"},
        headers=_auth_headers(admin_token),
    )
    grant.raise_for_status()
    assert grant.json()["status"] == "granted"
    assert grant.json().get("canonical_ledger_entry_id")

    grant_rows = (
        db_session.query(CanonicalCreditLedgerEntryRecord)
        .filter(
            CanonicalCreditLedgerEntryRecord.user_id == golden_demo_seed.user_id,
            CanonicalCreditLedgerEntryRecord.entry_type == "grant",
        )
        .all()
    )
    assert grant_rows
    assert credit_balance(db_session, golden_demo_seed.user_id) == 10

    login_resp = api_client.post(
        "/api/community/auth/login",
        json={"username": golden_demo_seed.username, "password": golden_demo_seed.password},
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]

    balance_resp = api_client.get("/api/canon/credits/balance", headers=_auth_headers(token))
    balance_resp.raise_for_status()
    assert balance_resp.json()["balance"] == 10

    export_resp = api_client.post(
        "/api/canon/exports",
        headers=_auth_headers(token),
        json=_canon_export_body(sources, "acceptance-export-1"),
    )
    export_resp.raise_for_status()
    assert export_resp.status_code == 201
    data = export_resp.json()
    assert data["export_id"]
    assert data["status"] == "queued"
    assert data["credit_cost"] == settings.patchbook_export_cost
    assert data["source_run_id"] == sources["source_run_id"]
    assert data["source_rig_revision_id"] == sources["source_rig_revision_id"]

    expected_balance = 10 - settings.patchbook_export_cost
    assert credit_balance(db_session, golden_demo_seed.user_id) == expected_balance

    debit_rows = (
        db_session.query(CanonicalCreditLedgerEntryRecord)
        .filter(
            CanonicalCreditLedgerEntryRecord.user_id == golden_demo_seed.user_id,
            CanonicalCreditLedgerEntryRecord.entry_type == "debit",
        )
        .all()
    )
    assert debit_rows
    assert any(row.export_id == data["export_id"] for row in debit_rows)

    export_record = db_session.get(CanonicalExportRecord, data["export_id"])
    assert export_record is not None
    assert export_record.user_id == golden_demo_seed.user_id

    # Idempotent retry: same key, no second debit.
    cached_resp = api_client.post(
        "/api/canon/exports",
        headers=_auth_headers(token),
        json=_canon_export_body(sources, "acceptance-export-1"),
    )
    cached_resp.raise_for_status()
    cached_data = cached_resp.json()
    assert cached_data["export_id"] == data["export_id"]
    assert credit_balance(db_session, golden_demo_seed.user_id) == expected_balance


def test_failed_export_compensates_without_net_spend(export_fulfillment_pending, 
    api_client, db_session: Session, golden_demo_seed, admin_user
):
    """Terminal failure after debit is reversed via one immutable compensation entry."""
    sources = _attach_canon_export_sources(db_session, run_id=golden_demo_seed.run_id)

    admin_login = api_client.post(
        "/api/community/auth/login",
        json={"username": admin_user.username, "password": "admin-pass"},
    )
    admin_login.raise_for_status()
    admin_token = admin_login.json()["access_token"]

    api_client.post(
        f"/api/admin/users/{golden_demo_seed.user_id}/credits/grant",
        json={"credits": 5, "reason": "acceptance-fail-path"},
        headers=_auth_headers(admin_token),
    ).raise_for_status()

    login_resp = api_client.post(
        "/api/community/auth/login",
        json={"username": golden_demo_seed.username, "password": golden_demo_seed.password},
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]

    export_resp = api_client.post(
        "/api/canon/exports",
        headers=_auth_headers(token),
        json=_canon_export_body(sources, "acceptance-export-fail-1"),
    )
    export_resp.raise_for_status()
    export_id = export_resp.json()["export_id"]
    assert (
        credit_balance(db_session, golden_demo_seed.user_id) == 5 - settings.patchbook_export_cost
    )

    export_row = db_session.get(CanonicalExportRecord, export_id)
    assert export_row is not None
    compensate_failed_export(
        db_session,
        export_row,
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.commit()
    db_session.refresh(export_row)

    assert str(export_row.status) == "refunded"
    assert credit_balance(db_session, golden_demo_seed.user_id) == 5

    reversals = (
        db_session.query(CanonicalCreditLedgerEntryRecord)
        .filter(
            CanonicalCreditLedgerEntryRecord.user_id == golden_demo_seed.user_id,
            CanonicalCreditLedgerEntryRecord.entry_type == "reversal",
        )
        .all()
    )
    assert len(reversals) == 1
    assert reversals[0].export_id == export_id
