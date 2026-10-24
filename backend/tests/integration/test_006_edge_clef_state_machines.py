"""Integration tests for the Spec 006 decision and edge readiness state machines.

Every test is deterministic and offline: Clef is exercised through an
httpx.MockTransport client, the 4xx/5xx failure paths are simulated, and the
edge readiness machine is replayed from receipted evidence only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from canon.models import (
    ClassificationEvidenceRecord,
    ImageAssetRecord,
    SystemInventoryRevisionRecord,
)
from core import get_db, settings
from core.config import Settings
from core.database import Base
from core.ops.edge_readiness import (
    ReadinessEvent,
    ReadinessEvidence,
    ReadinessState,
    config_gate_checks,
    live_payments_permitted,
    production_claims_permitted,
    replay_readiness,
)
from intelligence.clef_provider import ClefDecisionProvider, ClefImage
from intelligence.clef_resolution import (
    PolicyVersionNotPinned,
    archive,
    confirm_via_existing_path,
    resolve_module_identity_guarded,
)
from intelligence.contracts import DecisionPacket
from intelligence.evidence_resolution import DecisionIntelligenceDisabled
from intelligence.fixture_provider import FixtureDecisionProvider, failed_fixture
from intelligence.models import DecisionReceiptRecord
from intelligence.policy import DecisionPolicy, PolicyThresholds
from intelligence.resolution_machine import (
    FINAL_STATES,
    ResolutionMachine,
    ResolutionState,
    canon_write_permitted,
)
from main import app

REQUEST_ID = "module-identity:ev-1"

# Every machine this module produces must end in a FINAL_STATES member.
_PRODUCED_MACHINES: list[ResolutionMachine] = []


# ---------------------------------------------------------------------------
# Local DB helpers (mirrors backend/tests/unit/test_evidence_resolution.py)
# ---------------------------------------------------------------------------


def _policy() -> DecisionPolicy:
    return DecisionPolicy(PolicyThresholds(
        policy_version="test-v1",
        auto_propose_at=0.9,
        user_review_at=0.65,
        probability_margin=0.1,
    ))


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db, *, evidence_id: str = "ev-1", candidate_evidence_id: str = "ev-1"):
    now = datetime.now(timezone.utc)
    db.add(ImageAssetRecord(
        id="img-1", rack_id=1, user_id=1, content_sha256="a" * 64,
        media_type="image/jpeg", width=100, height=100, byte_length=10,
        storage_path="/tmp/none", retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False, created_at=now,
    ))
    raw = {
        "candidate_id": "module-a", "entity_type": "module",
        "manufacturer": "Make", "model": "Alpha", "confidence": 0.8,
        "confidence_method": "fixture", "classification_status": "INFERRED",
        "evidence_id": candidate_evidence_id,
    }
    db.add(ClassificationEvidenceRecord(
        id=evidence_id, image_asset_id="img-1", inventory_revision_id=None,
        evidence_packet={"devices": [raw]}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db.flush()


# ---------------------------------------------------------------------------
# Clef helpers: envelope, mock transport, guarded resolution
# ---------------------------------------------------------------------------


def _envelope(choice: str, confidence: float, probabilities: dict) -> dict:
    return {
        "success": True,
        "result": {
            "answers": {
                "q0": {
                    "type": "choice",
                    "choice": choice,
                    "confidence": confidence,
                    "probabilities": probabilities,
                },
            },
        },
    }


def _mock_provider(handler, **kwargs) -> ClefDecisionProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ClefDecisionProvider(
        enabled=True,
        account_id="acct-test",
        api_token="tok-test",
        client=client,
        **kwargs,
    )


def _ok_handler(choice="module-a", confidence=0.95, probabilities=None, calls=None):
    probs = probabilities or {
        "module-a": confidence,
        "none_of_above": round(1.0 - confidence, 6),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(200, json=_envelope(choice, confidence, probs))

    return handler


def _timeout_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("clef request timed out")

    return handler


def _unavailable_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"success": False, "errors": [{"code": 1}]})

    return handler


def _malformed_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(
            "ghost-choice", 0.9, {"ghost-choice": 0.9, "none_of_above": 0.1}
        ))

    return handler


def _resolve_clef(db, handler, *, provider_kwargs=None, idempotency_key="idem"):
    provider = _mock_provider(handler, **(provider_kwargs or {}))
    return resolve_module_identity_guarded(
        db,
        evidence_id="ev-1",
        provider=provider,
        policy=_policy(),
        enabled=True,
        idempotency_key=idempotency_key,
        expected_policy_version="test-v1",
    )


def _resolve_with(db, provider):
    return resolve_module_identity_guarded(
        db,
        evidence_id="ev-1",
        provider=provider,
        policy=_policy(),
        enabled=True,
        idempotency_key="idem",
        expected_policy_version="test-v1",
    )


def _telemetry_category(telemetry) -> str:
    category = telemetry.category
    return str(getattr(category, "value", category))


# ---------------------------------------------------------------------------
# (a) Flag-off default: CLEF_DISABLED, fail closed, no network, no receipts
# ---------------------------------------------------------------------------


def test_clef_flag_off_default_fails_closed_without_network() -> None:
    db = _db()
    _seed(db)

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_envelope(
            "module-a", 0.95, {"module-a": 0.95, "none_of_above": 0.05}
        ))

    unused_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        provider = ClefDecisionProvider()  # inert: no args, flag off
        resolution = _resolve_with(db, provider)
    finally:
        unused_client.close()

    _PRODUCED_MACHINES.append(resolution.machine)
    assert resolution.machine.state is ResolutionState.REJECT
    assert resolution.error_code == "CLEF_DISABLED"
    assert resolution.proposal is None
    assert resolution.receipt_id is None
    assert _telemetry_category(resolution.telemetry) == "DISABLED"
    assert calls == []
    assert db.query(DecisionReceiptRecord).count() == 0
    assert db.query(SystemInventoryRevisionRecord).count() == 0


# ---------------------------------------------------------------------------
# (b) enabled=False raises before any provider or DB work
# ---------------------------------------------------------------------------


def test_guard_flow_disabled_flag_raises_before_provider_call() -> None:
    db = _db()
    _seed(db)

    class NeverProvider:
        def choose(self, request):
            raise AssertionError("provider must not be called")

        def score(self, request):
            raise AssertionError("provider must not be called")

        def probability(self, request):
            raise AssertionError("provider must not be called")

    with pytest.raises(DecisionIntelligenceDisabled):
        resolve_module_identity_guarded(
            db,
            evidence_id="ev-1",
            provider=NeverProvider(),
            policy=_policy(),
            enabled=False,
            idempotency_key="idem",
            expected_policy_version="test-v1",
        )
    assert db.query(DecisionReceiptRecord).count() == 0


# ---------------------------------------------------------------------------
# (c) Unpinned policy version raises before the provider is called
# ---------------------------------------------------------------------------


def test_unpinned_policy_version_raises_before_provider_call() -> None:
    db = _db()
    _seed(db)
    calls: list[httpx.Request] = []

    provider = _mock_provider(_ok_handler(calls=calls))

    with pytest.raises(PolicyVersionNotPinned):
        resolve_module_identity_guarded(
            db,
            evidence_id="ev-1",
            provider=provider,
            policy=_policy(),
            enabled=True,
            idempotency_key="idem",
            expected_policy_version="other",
        )
    assert calls == []
    assert db.query(DecisionReceiptRecord).count() == 0


# ---------------------------------------------------------------------------
# (d) Success paths: every reachable disposition, policy-owned
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "choice,confidence,probabilities,expected_disposition,expected_telemetry",
    [
        ("module-a", 0.95, {"module-a": 0.95, "none_of_above": 0.05}, "AUTO_PROPOSE", None),
        ("module-a", 0.7, {"module-a": 0.7, "none_of_above": 0.3}, "USER_REVIEW", None),
        ("module-a", 0.5, {"module-a": 0.5, "none_of_above": 0.5}, "UNRESOLVED", None),
        (
            "none_of_above",
            0.8,
            {"module-a": 0.2, "none_of_above": 0.8},
            "UNRESOLVED",
            "ABSTAINED",
        ),
    ],
)
def test_clef_success_paths_follow_policy(
    choice, confidence, probabilities, expected_disposition, expected_telemetry
) -> None:
    db = _db()
    _seed(db)

    resolution = _resolve_clef(
        db,
        _ok_handler(choice=choice, confidence=confidence, probabilities=probabilities),
    )
    _PRODUCED_MACHINES.append(resolution.machine)

    assert resolution.error_code is None
    assert resolution.proposal is not None
    disposition = resolution.proposal.policy.disposition
    assert disposition.value == expected_disposition
    assert resolution.machine.state.value == expected_disposition
    assert resolution.machine.history[-1].to_state is resolution.machine.state
    assert resolution.machine.history[-1].accepted is True
    assert canon_write_permitted(resolution.machine) is False
    assert resolution.canonical_authority is False
    assert resolution.proposal.packet.selected_choice == choice

    receipt = db.query(DecisionReceiptRecord).one()
    assert receipt.id == resolution.receipt_id
    assert receipt.disposition == disposition.value
    assert receipt.provider == "clef"
    assert receipt.evidence_hash == "ev-1"
    assert db.query(SystemInventoryRevisionRecord).count() == 0

    if expected_telemetry is not None:
        assert _telemetry_category(resolution.telemetry) == expected_telemetry


# ---------------------------------------------------------------------------
# (e) Idempotency: same Clef response yields one receipt and one receipt id
# ---------------------------------------------------------------------------


def test_repeated_clef_resolution_is_idempotent() -> None:
    db = _db()
    _seed(db)
    handler = _ok_handler()

    first = _resolve_clef(db, handler)
    second = _resolve_clef(db, handler)
    _PRODUCED_MACHINES.extend([first.machine, second.machine])

    assert first.receipt_id is not None
    assert first.receipt_id == second.receipt_id
    assert db.query(DecisionReceiptRecord).count() == 1
    assert db.query(SystemInventoryRevisionRecord).count() == 0


# ---------------------------------------------------------------------------
# (f) Fail-closed provider failures persist no receipt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "handler_factory,expected_code",
    [
        (_timeout_handler, "CLEF_TIMEOUT"),
        (_unavailable_handler, "CLEF_UNAVAILABLE"),
        (_malformed_handler, "CLEF_MALFORMED"),
    ],
)
def test_clef_provider_failures_fail_closed(handler_factory, expected_code) -> None:
    db = _db()
    _seed(db)

    resolution = _resolve_clef(db, handler_factory())
    _PRODUCED_MACHINES.append(resolution.machine)

    assert resolution.machine.state is ResolutionState.REJECT
    assert resolution.error_code == expected_code
    assert resolution.proposal is None
    assert resolution.receipt_id is None
    assert db.query(DecisionReceiptRecord).count() == 0
    assert db.query(SystemInventoryRevisionRecord).count() == 0

    if expected_code == "CLEF_TIMEOUT":
        assert _telemetry_category(resolution.telemetry) == "PROVIDER_FAILURE"
        assert getattr(resolution.telemetry, "adapter_state", None) == "TIMEOUT"


def test_packet_with_wrong_candidate_set_hash_is_rejected() -> None:
    db = _db()
    _seed(db)
    packet = DecisionPacket(
        decision_id="wrong-hash",
        request_id=REQUEST_ID,
        provider="fixture",
        provider_version="1",
        evidence_hash="ev-1",
        answer_type="choice",
        selected_choice="module-a",
        probabilities={"module-a": 0.95, "none_of_above": 0.05},
        confidence=0.95,
        candidate_set_hash="0" * 64,
        created_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
    )
    class _UncheckedProvider:
        """Returns the packet verbatim so the guarded flow's own schema guard is exercised."""

        provider_version = "unchecked-1"

        def choose(self, request):
            return packet

        def score(self, request):
            raise AssertionError("score not used")

        def probability(self, request):
            raise AssertionError("probability not used")

    resolution = _resolve_with(db, _UncheckedProvider())
    _PRODUCED_MACHINES.append(resolution.machine)

    assert resolution.machine.state is ResolutionState.REJECT
    assert resolution.error_code == "PACKET_SCHEMA_INVALID"
    assert resolution.receipt_id is None
    assert db.query(DecisionReceiptRecord).count() == 0
    assert db.query(SystemInventoryRevisionRecord).count() == 0


def test_failed_packet_is_rejected_without_receipt() -> None:
    db = _db()
    _seed(db)
    packet = failed_fixture(
        decision_id="failed-1",
        request_id=REQUEST_ID,
        provider_status="failed",
        evidence_hash="ev-1",
        error_code="FIXTURE_FAILURE",
    )
    provider = FixtureDecisionProvider({REQUEST_ID: packet})

    resolution = _resolve_with(db, provider)
    _PRODUCED_MACHINES.append(resolution.machine)

    assert resolution.machine.state is ResolutionState.REJECT
    assert resolution.error_code is not None
    assert resolution.receipt_id is None
    assert db.query(DecisionReceiptRecord).count() == 0
    assert db.query(SystemInventoryRevisionRecord).count() == 0


# ---------------------------------------------------------------------------
# (g) No canonical authority before CONFIRMED; archive lifecycle
# ---------------------------------------------------------------------------


def test_no_canon_write_before_confirmed_and_archive_lifecycle() -> None:
    db = _db()
    _seed(db)

    resolution = _resolve_clef(db, _ok_handler())
    assert resolution.state is ResolutionState.AUTO_PROPOSE
    assert canon_write_permitted(resolution.machine) is False
    assert db.query(SystemInventoryRevisionRecord).count() == 0

    unconfirmed = confirm_via_existing_path(resolution, confirmation_path_used=False)
    assert unconfirmed.state is ResolutionState.AUTO_PROPOSE
    assert canon_write_permitted(unconfirmed) is False
    assert db.query(SystemInventoryRevisionRecord).count() == 0

    confirmed = confirm_via_existing_path(resolution, confirmation_path_used=True)
    assert confirmed.state is ResolutionState.CONFIRMED
    assert canon_write_permitted(confirmed) is True

    confirmed_resolution = replace(resolution, machine=confirmed)
    archived = archive(confirmed_resolution)
    assert archived.state is ResolutionState.ARCHIVED

    archived_again = archive(replace(confirmed_resolution, machine=archived))
    assert archived_again.state is ResolutionState.ARCHIVED
    assert archived_again.history[-1].accepted is False
    assert archived_again.history[-1].reason == "ARCHIVED_IMMUTABLE"

    _PRODUCED_MACHINES.extend([resolution.machine, unconfirmed, confirmed, archived])


def test_reject_resolution_cannot_be_confirmed_and_can_be_archived() -> None:
    db = _db()
    _seed(db)

    resolution = _resolve_clef(db, _timeout_handler())
    assert resolution.state is ResolutionState.REJECT
    assert resolution.error_code == "CLEF_TIMEOUT"

    still_rejected = confirm_via_existing_path(resolution, confirmation_path_used=True)
    assert still_rejected.state is ResolutionState.REJECT
    assert canon_write_permitted(still_rejected) is False

    archived = archive(replace(resolution, machine=still_rejected))
    assert archived.state is ResolutionState.ARCHIVED

    _PRODUCED_MACHINES.extend([resolution.machine, still_rejected, archived])


# ---------------------------------------------------------------------------
# (h) No raw image bytes or secrets cross into packets or receipts
# ---------------------------------------------------------------------------


def _loader_image() -> ClefImage:
    return ClefImage("image/png", b"\x89PNG\r\n\x1a\n" + b"0" * 32)


def test_receipts_and_packets_contain_no_raw_bytes_or_secrets() -> None:
    db = _db()
    _seed(db)

    def image_loader(request):
        return [_loader_image()]

    resolution = _resolve_clef(
        db, _ok_handler(), provider_kwargs={"image_loader": image_loader}
    )
    _PRODUCED_MACHINES.append(resolution.machine)

    assert resolution.proposal is not None
    receipt = db.query(DecisionReceiptRecord).one()

    blobs: list[str] = [resolution.proposal.packet.model_dump_json()]
    for column in DecisionReceiptRecord.__table__.columns:
        value = getattr(receipt, column.name)
        if isinstance(value, str):
            blobs.append(value)
        else:
            blobs.append(json.dumps(value, default=str))

    for blob in blobs:
        assert "tok-test" not in blob
        assert "base64" not in blob
        assert "iVBOR" not in blob


# ---------------------------------------------------------------------------
# (i) API route: guarded Clef flow is advisory only; failures map to status
# ---------------------------------------------------------------------------


def _seed_api_evidence(db, rack, evidence_id: str) -> str:
    now = datetime.now(timezone.utc)
    asset_id = f"img-{evidence_id}"
    digest = hashlib.sha256(evidence_id.encode("utf-8")).hexdigest()
    db.add(ImageAssetRecord(
        id=asset_id, rack_id=rack.id, user_id=rack.user_id, content_sha256=digest,
        media_type="image/jpeg", width=100, height=100, byte_length=10,
        storage_path=f"/tmp/{asset_id}.jpg", retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False, created_at=now,
    ))
    candidate = {
        "candidate_id": "module-a", "entity_type": "module",
        "manufacturer": "Make", "model": "Alpha", "confidence": 0.8,
        "confidence_method": "fixture", "classification_status": "INFERRED",
        "evidence_id": evidence_id,
    }
    db.add(ClassificationEvidenceRecord(
        id=evidence_id, image_asset_id=asset_id, inventory_revision_id=None,
        evidence_packet={"devices": [candidate]}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db.commit()
    return evidence_id


def _post_resolution(db_session, rack_id: int, evidence_id: str, idem: str):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        return TestClient(app).post(
            f"/api/racks/{rack_id}/evidence/decision-resolution",
            json={"evidence_id": evidence_id, "idempotency_key": idem},
        )
    finally:
        app.dependency_overrides.clear()


def test_api_clef_guarded_success_is_advisory_only(
    db_session, sample_rack_basic, monkeypatch
) -> None:
    import evidence.routes as routes

    evidence_id = "ev-di-clef-ok"
    _seed_api_evidence(db_session, sample_rack_basic, evidence_id)
    provider = _mock_provider(_ok_handler())

    monkeypatch.setattr(routes, "_configured_decision_provider", lambda: provider)
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    monkeypatch.setattr(settings, "decision_provider", "clef")

    before = db_session.query(SystemInventoryRevisionRecord).count()
    response = _post_resolution(
        db_session, sample_rack_basic.id, evidence_id, "clef-api-ok"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "clef"
    assert body["canonical_authority"] is False
    assert body["selected_choice"] == "module-a"
    assert db_session.query(DecisionReceiptRecord).count() == 1
    assert db_session.query(SystemInventoryRevisionRecord).count() == before


def test_api_clef_flag_off_returns_409(
    db_session, sample_rack_basic, monkeypatch
) -> None:
    import evidence.routes as routes

    evidence_id = "ev-di-clef-off"
    _seed_api_evidence(db_session, sample_rack_basic, evidence_id)

    monkeypatch.setattr(
        routes, "_configured_decision_provider", lambda: ClefDecisionProvider()
    )
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    monkeypatch.setattr(settings, "decision_provider", "clef")

    response = _post_resolution(
        db_session, sample_rack_basic.id, evidence_id, "clef-api-off"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "CLEF_DISABLED"
    assert db_session.query(DecisionReceiptRecord).count() == 0


def test_api_clef_timeout_returns_504(
    db_session, sample_rack_basic, monkeypatch
) -> None:
    import evidence.routes as routes

    evidence_id = "ev-di-clef-timeout"
    _seed_api_evidence(db_session, sample_rack_basic, evidence_id)
    provider = _mock_provider(_timeout_handler())

    monkeypatch.setattr(routes, "_configured_decision_provider", lambda: provider)
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    monkeypatch.setattr(settings, "decision_provider", "clef")

    response = _post_resolution(
        db_session, sample_rack_basic.id, evidence_id, "clef-api-timeout"
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "CLEF_TIMEOUT"
    assert db_session.query(DecisionReceiptRecord).count() == 0


def test_settings_clef_flag_defaults_off() -> None:
    assert Settings.model_fields["enable_clef_provider"].default is False


# ---------------------------------------------------------------------------
# (j) Edge readiness deployment machine
# ---------------------------------------------------------------------------


READINESS_STEPS: tuple[ReadinessEvent, ...] = (
    ReadinessEvent.PAGES_DEPLOYED,
    ReadinessEvent.API_PUBLISHED,
    ReadinessEvent.HYPERDRIVE_BOUND,
    ReadinessEvent.CLEF_ADAPTER_WIRED,
    ReadinessEvent.GATES_PASS,
    ReadinessEvent.OPERATOR_APPROVE,
)


def _complete_evidence(**overrides) -> ReadinessEvidence:
    base = dict(
        pages_build_output_present=True,
        pages_custom_domain_attached=True,
        api_cors_exact_origin=True,
        api_health_ok=True,
        payments_live_disabled=True,
        hyperdrive_neon_staging=True,
        d1_absent=True,
        clef_flag_default_off=True,
        staging_host_plan_passed=True,
        evaluation_receipt_sha256="a" * 64,
        operator_approved=True,
        checklist_receipts=("receipt-1",),
    )
    base.update(overrides)
    return ReadinessEvidence(**base)


def test_readiness_replay_reaches_beta_ready() -> None:
    state, results = replay_readiness(
        (event, _complete_evidence()) for event in READINESS_STEPS
    )

    assert state is ReadinessState.BETA_READY
    assert all(result.accepted for result in results)
    assert production_claims_permitted(state) is True
    assert live_payments_permitted(state) is False


def test_readiness_replay_stops_at_gates_without_operator_approval() -> None:
    state, results = replay_readiness(
        (event, _complete_evidence(operator_approved=False)) for event in READINESS_STEPS
    )

    assert state is ReadinessState.GATES_PASSED
    assert results[-1].accepted is False
    assert "OPERATOR_APPROVAL_MISSING" in results[-1].failed_checks
    assert production_claims_permitted(state) is False


def test_config_gates_report_operator_locked_origin() -> None:
    checks = {
        check.code: check
        for check in config_gate_checks(settings, expected_frontend_origin=None)
    }

    assert checks["PAYMENTS_LIVE_DISABLED"].passed is True
    assert checks["CLEF_FLAG_DEFAULT_OFF"].passed is True
    assert checks["CORS_EXACT_ORIGIN"].passed is False
    assert "OPERATOR_LOCKED" in checks["CORS_EXACT_ORIGIN"].detail


@pytest.mark.skip(
    reason=(
        "T030/T040/T050 operator Cloudflare actions (Pages, API hostname + CORS, "
        "Hyperdrive to Neon staging) are deferred and operator-locked; live edge "
        "readiness cannot be probed from CI"
    )
)
def test_live_edge_readiness_requires_operator_cloudflare_actions() -> None:
    raise AssertionError("live edge readiness is not probeable from CI")


# ---------------------------------------------------------------------------
# Invariant sweep: every machine produced above ends in a final state
# ---------------------------------------------------------------------------


def test_every_resolution_in_this_module_ends_in_a_final_state() -> None:
    assert _PRODUCED_MACHINES
    for machine in _PRODUCED_MACHINES:
        assert machine.state in FINAL_STATES, machine.state
