"""Integration tests for the Spec 006 Clef vision-image wiring.

A review finding said the Clef factory never supplied an image_loader, so vision
ranking never happened. These tests prove the fix end to end:

* the retention- and consent-gated loader is lazy and never touches the session
  or the filesystem at construction time;
* the adapter accepts ``EvidenceImage`` payloads and fails closed
  (``CLEF_UNAVAILABLE``, no network) whenever the loader raises;
* the route builds the loader only when ``settings.enable_clef_provider`` is True
  and forwards it through ``_configured_decision_provider(image_loader=...)``;
* no raw bytes, base64 blobs, or secrets ever reach packets, receipts, telemetry,
  or log records.

Everything is deterministic and offline: Clef is exercised through an
``httpx.MockTransport`` client and every image is a real file under ``tmp_path``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
from core.database import Base
from intelligence.clef_provider import ClefDecisionProvider, ClefProviderError
from intelligence.clef_resolution import resolve_module_identity_guarded
from intelligence.clef_telemetry import to_log_record
from intelligence.evidence_images import (
    BoundEvidenceImageLoader,
    EvidenceImage,
    ImageAccessDecision,
    image_access_decision,
)
from intelligence.models import DecisionReceiptRecord
from intelligence.policy import DecisionPolicy, PolicyThresholds
from intelligence.resolution_machine import ResolutionState
from main import app

IMAGE_BYTES = b"\xff\xd8\xff\xe0" + b"patchhive-test-image" * 4
IMAGE_SHA256 = hashlib.sha256(IMAGE_BYTES).hexdigest()
IMAGE_B64 = base64.b64encode(IMAGE_BYTES).decode("ascii")
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
TELEMETRY_LOGGER = "patchhive.decision.telemetry"


# ---------------------------------------------------------------------------
# Local DB / policy / seed helpers (mirrors the Spec 006 integration module)
# ---------------------------------------------------------------------------


def _policy() -> DecisionPolicy:
    return DecisionPolicy(
        PolicyThresholds(
            policy_version="test-v1",
            auto_propose_at=0.9,
            user_review_at=0.65,
            probability_margin=0.1,
        )
    )


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _write_image(root: Path, name: str = "image.jpg") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_bytes(IMAGE_BYTES)
    return path


def _seed(
    db,
    *,
    evidence_id: str = "ev-1",
    asset_id: str = "img-1",
    candidate_evidence_id: str | None = None,
    consent: bool = True,
    expires_delta: timedelta = timedelta(days=30),
    deleted: bool = False,
    storage_path: str = "/tmp/none",
    content_sha256: str = "a" * 64,
    media_type: str = "image/jpeg",
) -> None:
    now = datetime.now(timezone.utc)
    db.add(
        ImageAssetRecord(
            id=asset_id,
            rack_id=1,
            user_id=1,
            content_sha256=content_sha256,
            media_type=media_type,
            width=100,
            height=100,
            byte_length=len(IMAGE_BYTES),
            storage_path=storage_path,
            retention_days=30,
            retention_expires_at=now + expires_delta,
            consent_provider_processing=consent,
            deleted_at=now if deleted else None,
            created_at=now,
        )
    )
    raw = {
        "candidate_id": "module-a",
        "entity_type": "module",
        "manufacturer": "Make",
        "model": "Alpha",
        "confidence": 0.8,
        "confidence_method": "fixture",
        "classification_status": "INFERRED",
        "evidence_id": candidate_evidence_id or evidence_id,
    }
    db.add(
        ClassificationEvidenceRecord(
            id=evidence_id,
            image_asset_id=asset_id,
            inventory_revision_id=None,
            evidence_packet={"devices": [raw]},
            provider="fixture-vision",
            pipeline_version="vision-v1",
            status="INFERRED",
            created_at=now,
        )
    )
    db.flush()


# ---------------------------------------------------------------------------
# Clef helpers: envelope, recording transport, guarded resolution
# ---------------------------------------------------------------------------


def _envelope(choice: str, confidence: float, probabilities: dict) -> dict:
    return {
        "success": True,
        "result": {
            "answers": {
                "q0": {
                    "type": "choice",
                    "choice": choice,
                    "probabilities": probabilities,
                    "confidence": confidence,
                },
            },
        },
    }


def _recording_handler(
    calls: list[dict],
    *,
    choice: str = "module-a",
    confidence: float = 0.95,
    probabilities: dict | None = None,
):
    probs = probabilities or {
        "module-a": confidence,
        "none_of_above": round(1.0 - confidence, 6),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=_envelope(choice, confidence, probs))

    return handler


def _mock_provider(handler, **kwargs) -> ClefDecisionProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ClefDecisionProvider(
        enabled=True,
        account_id="acct-test",
        api_token="tok-test",
        client=client,
        **kwargs,
    )


def _resolve_with(db, provider, *, evidence_id: str = "ev-1", idempotency_key: str = "idem"):
    return resolve_module_identity_guarded(
        db,
        evidence_id=evidence_id,
        provider=provider,
        policy=_policy(),
        enabled=True,
        idempotency_key=idempotency_key,
        expected_policy_version="test-v1",
    )


def _asset(**overrides) -> SimpleNamespace:
    base = {
        "deleted_at": None,
        "retention_expires_at": NOW + timedelta(days=30),
        "consent_provider_processing": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _ExplodingDb:
    """Session stand-in that fails loudly if the loader touches it eagerly."""

    def __getattr__(self, name: str):
        raise AssertionError(f"loader touched the session: {name}")


# ---------------------------------------------------------------------------
# (1) Pure access decision: consent + retention, naive datetimes as UTC
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "asset,expected",
    [
        pytest.param(None, ImageAccessDecision.ASSET_MISSING, id="missing"),
        pytest.param(
            _asset(deleted_at=NOW - timedelta(hours=1)),
            ImageAccessDecision.ASSET_DELETED,
            id="deleted",
        ),
        pytest.param(
            _asset(retention_expires_at=NOW - timedelta(seconds=1)),
            ImageAccessDecision.RETENTION_EXPIRED,
            id="expired",
        ),
        pytest.param(
            _asset(retention_expires_at=NOW),
            ImageAccessDecision.RETENTION_EXPIRED,
            id="expires-exactly-now",
        ),
        pytest.param(
            _asset(retention_expires_at=(NOW - timedelta(days=1)).replace(tzinfo=None)),
            ImageAccessDecision.RETENTION_EXPIRED,
            id="naive-expired",
        ),
        pytest.param(
            _asset(retention_expires_at=(NOW + timedelta(days=1)).replace(tzinfo=None)),
            ImageAccessDecision.CLEARED,
            id="naive-future",
        ),
        pytest.param(
            _asset(consent_provider_processing=False),
            ImageAccessDecision.CONSENT_NOT_GRANTED,
            id="no-consent",
        ),
        pytest.param(_asset(), ImageAccessDecision.CLEARED, id="cleared"),
    ],
)
def test_image_access_decision(asset, expected) -> None:
    assert image_access_decision(asset, now=NOW) is expected


# ---------------------------------------------------------------------------
# (2) Loader construction performs no I/O
# ---------------------------------------------------------------------------


def test_loader_construction_is_lazy(tmp_path) -> None:
    loader = BoundEvidenceImageLoader(
        _ExplodingDb(), evidence_id="ev-1", storage_root=tmp_path / "evidence"
    )

    assert loader.calls == 0
    assert loader.load_count == 0
    assert loader.last_decision is None


# ---------------------------------------------------------------------------
# (3) Flag on + consent-cleared asset: bytes reach the request, never the packet
# ---------------------------------------------------------------------------


def test_clef_sends_consent_cleared_image(tmp_path) -> None:
    db = _db()
    image_path = _write_image(tmp_path / "evidence")
    _seed(db, storage_path=str(image_path), content_sha256=IMAGE_SHA256)

    calls: list[dict] = []
    loader = BoundEvidenceImageLoader(
        db, evidence_id="ev-1", storage_root=tmp_path / "evidence"
    )
    provider = _mock_provider(_recording_handler(calls), image_loader=loader)

    resolution = _resolve_with(db, provider)

    assert len(calls) == 1
    assert calls[0]["images"] == [f"data:image/jpeg;base64,{IMAGE_B64}"]
    assert loader.calls == 1
    assert loader.load_count == 1
    assert loader.last_decision is ImageAccessDecision.CLEARED

    assert resolution.error_code is None
    assert resolution.proposal is not None
    disposition = resolution.proposal.policy.disposition
    assert disposition.value == "AUTO_PROPOSE"
    assert resolution.machine.state.value == "AUTO_PROPOSE"
    assert resolution.proposal.packet.selected_choice == "module-a"
    assert resolution.canonical_authority is False

    assert db.query(DecisionReceiptRecord).count() == 1
    assert db.query(SystemInventoryRevisionRecord).count() == 0


# ---------------------------------------------------------------------------
# (4) No raw bytes, base64 blobs, or secrets cross the boundary
# ---------------------------------------------------------------------------


def _leak_tokens() -> list[str]:
    return [IMAGE_B64, "base64", "patchhive-test-image", "tok-test"]


def test_no_image_bytes_or_secrets_leak(tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO, logger=TELEMETRY_LOGGER)

    db = _db()
    image_path = _write_image(tmp_path / "evidence")
    _seed(db, storage_path=str(image_path), content_sha256=IMAGE_SHA256)

    calls: list[dict] = []
    loader = BoundEvidenceImageLoader(
        db, evidence_id="ev-1", storage_root=tmp_path / "evidence"
    )
    provider = _mock_provider(_recording_handler(calls), image_loader=loader)

    resolution = _resolve_with(db, provider)

    assert resolution.proposal is not None
    assert len(calls) == 1

    receipt = db.query(DecisionReceiptRecord).one()
    blobs: list[str] = [
        resolution.proposal.packet.model_dump_json(),
        json.dumps(to_log_record(resolution.telemetry)),
    ]
    for column in DecisionReceiptRecord.__table__.columns:
        blobs.append(str(getattr(receipt, column.name)))
    blobs.append(caplog.text)

    for blob in blobs:
        for token in _leak_tokens():
            assert token not in blob, token

    image = EvidenceImage(content_type="image/jpeg", data=IMAGE_BYTES)
    rendered = repr(image)
    assert "patchhive-test-image" not in rendered
    assert IMAGE_B64 not in rendered


# ---------------------------------------------------------------------------
# (5) Flag off: loader is never invoked and no network call is made
# ---------------------------------------------------------------------------


def test_flag_off_never_invokes_loader_or_network(tmp_path) -> None:
    db = _db()
    image_path = _write_image(tmp_path / "evidence")
    _seed(db, storage_path=str(image_path), content_sha256=IMAGE_SHA256)

    def exploding_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no network call is permitted while the flag is off")

    client = httpx.Client(transport=httpx.MockTransport(exploding_handler))
    loader = BoundEvidenceImageLoader(
        db, evidence_id="ev-1", storage_root=tmp_path / "evidence"
    )
    provider = ClefDecisionProvider(
        enabled=False,
        account_id="acct-test",
        api_token="tok-test",
        client=client,
        image_loader=loader,
    )

    resolution = _resolve_with(db, provider)

    assert resolution.state is ResolutionState.UNRESOLVED
    assert resolution.error_code == "CLEF_DISABLED"
    assert loader.calls == 0
    assert loader.load_count == 0
    assert loader.last_decision is None
    assert db.query(DecisionReceiptRecord).count() == 0

    spied: list[Any] = []

    def spy_loader(request):
        spied.append(request)
        raise AssertionError("the default inert provider must not load images")

    inert = ClefDecisionProvider(image_loader=spy_loader)
    second = _resolve_with(db, inert)

    assert second.error_code == "CLEF_DISABLED"
    assert spied == []
    assert inert.last_state.value == "IDLE"
    assert db.query(DecisionReceiptRecord).count() == 0


# ---------------------------------------------------------------------------
# (6) Loader failures fail closed: no network, no receipt, UNAVAILABLE state
# ---------------------------------------------------------------------------


def _case_sha_mismatch(tmp_path: Path) -> tuple[dict, dict]:
    path = _write_image(tmp_path / "evidence")
    return {"storage_path": str(path), "content_sha256": "0" * 64}, {}


def _case_missing_file(tmp_path: Path) -> tuple[dict, dict]:
    root = tmp_path / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    return {"storage_path": str(root / "missing.jpg"), "content_sha256": IMAGE_SHA256}, {}


def _case_outside_root(tmp_path: Path) -> tuple[dict, dict]:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(parents=True, exist_ok=True)
    path = elsewhere / "image.jpg"
    path.write_bytes(IMAGE_BYTES)
    return {"storage_path": str(path), "content_sha256": IMAGE_SHA256}, {}


def _case_too_large(tmp_path: Path) -> tuple[dict, dict]:
    path = _write_image(tmp_path / "evidence")
    return {"storage_path": str(path), "content_sha256": IMAGE_SHA256}, {"max_bytes": 4}


@pytest.mark.parametrize(
    "case",
    [_case_sha_mismatch, _case_missing_file, _case_outside_root, _case_too_large],
    ids=["sha-mismatch", "missing-file", "outside-root", "too-large"],
)
def test_loader_failure_fails_closed(tmp_path, case) -> None:
    db = _db()
    seed_kwargs, loader_kwargs = case(tmp_path)
    _seed(db, **seed_kwargs)

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=_envelope(
            "module-a", 0.95, {"module-a": 0.95, "none_of_above": 0.05}
        ))

    loader = BoundEvidenceImageLoader(
        db,
        evidence_id="ev-1",
        storage_root=tmp_path / "evidence",
        **loader_kwargs,
    )
    provider = _mock_provider(handler, image_loader=loader)

    resolution = _resolve_with(db, provider)

    assert calls == []
    assert loader.load_count == 0
    assert resolution.state is ResolutionState.UNRESOLVED
    assert resolution.error_code == "CLEF_UNAVAILABLE"
    assert resolution.proposal is None
    assert db.query(DecisionReceiptRecord).count() == 0
    assert resolution.telemetry.category.value == "PROVIDER_FAILURE"
    assert provider.last_state.value == "UNAVAILABLE"


def test_loader_exception_is_fail_closed_without_a_cause(tmp_path) -> None:
    db = _db()
    image_path = _write_image(tmp_path / "evidence")
    _seed(db, storage_path=str(image_path), content_sha256=IMAGE_SHA256)

    def boom(request):
        raise RuntimeError("boom /secret/path")

    handler_calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        handler_calls.append(request)
        return httpx.Response(200, json=_envelope(
            "module-a", 0.95, {"module-a": 0.95, "none_of_above": 0.05}
        ))

    provider = _mock_provider(handler, image_loader=boom)

    captured: dict[str, Any] = {}

    class _Recorder:
        """Captures the flow-built ChoiceRequest, then delegates to the real adapter."""

        provider_version = provider.provider_version

        def choose(self, request):
            captured["request"] = request
            return provider.choose(request)

        def score(self, request):
            raise AssertionError("score is not used")

        def probability(self, request):
            raise AssertionError("probability is not used")

    resolution = _resolve_with(db, _Recorder())
    assert resolution.error_code == "CLEF_UNAVAILABLE"
    assert resolution.state is ResolutionState.UNRESOLVED

    request = captured["request"]

    with pytest.raises(ClefProviderError) as excinfo:
        provider.choose(request)

    err = excinfo.value
    assert err.code == "CLEF_UNAVAILABLE"
    assert err.state.value == "UNAVAILABLE"
    assert err.__cause__ is None
    assert "secret" not in str(err)
    assert [state.value for state in provider.state_trace] == [
        "IDLE",
        "INVOKING",
        "UNAVAILABLE",
        "IDLE",
    ]
    assert handler_calls == []


# ---------------------------------------------------------------------------
# (7) Consent/retention denial: no file read, graceful text-only request
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides,expected_decision",
    [
        ({"consent": False}, ImageAccessDecision.CONSENT_NOT_GRANTED),
        ({"expires_delta": timedelta(days=-1)}, ImageAccessDecision.RETENTION_EXPIRED),
        ({"deleted": True}, ImageAccessDecision.ASSET_DELETED),
    ],
    ids=["no-consent", "expired", "deleted"],
)
def test_denied_asset_is_never_read(tmp_path, monkeypatch, overrides, expected_decision) -> None:
    db = _db()
    image_path = _write_image(tmp_path / "evidence")
    seed_kwargs = {"storage_path": str(image_path), "content_sha256": IMAGE_SHA256}
    seed_kwargs.update(overrides)
    _seed(db, **seed_kwargs)

    def exploding_read_bytes(self):
        raise AssertionError("a denied asset must never be read from disk")

    monkeypatch.setattr(Path, "read_bytes", exploding_read_bytes)

    calls: list[dict] = []
    loader = BoundEvidenceImageLoader(
        db, evidence_id="ev-1", storage_root=tmp_path / "evidence"
    )
    provider = _mock_provider(_recording_handler(calls), image_loader=loader)

    resolution = _resolve_with(db, provider)

    assert len(calls) == 1
    assert "images" not in calls[0]
    assert loader.calls == 1
    assert loader.load_count == 0
    assert loader.last_decision is expected_decision

    assert resolution.error_code is None
    assert resolution.proposal is not None
    assert resolution.proposal.packet.selected_choice == "module-a"
    assert db.query(DecisionReceiptRecord).count() == 1
    assert db.query(SystemInventoryRevisionRecord).count() == 0


# ---------------------------------------------------------------------------
# (8)/(9) Route wiring: loader supplied only when the Clef flag is on
# ---------------------------------------------------------------------------


def _seed_api_evidence(db, rack, *, evidence_id: str, asset_id: str, storage_root: Path) -> None:
    now = datetime.now(timezone.utc)
    image_path = _write_image(storage_root, name=f"{asset_id}.jpg")
    db.add(
        ImageAssetRecord(
            id=asset_id,
            rack_id=rack.id,
            user_id=rack.user_id,
            content_sha256=IMAGE_SHA256,
            media_type="image/jpeg",
            width=100,
            height=100,
            byte_length=len(IMAGE_BYTES),
            storage_path=str(image_path),
            retention_days=30,
            retention_expires_at=now + timedelta(days=30),
            consent_provider_processing=True,
            created_at=now,
        )
    )
    candidate = {
        "candidate_id": "module-a",
        "entity_type": "module",
        "manufacturer": "Make",
        "model": "Alpha",
        "confidence": 0.8,
        "confidence_method": "fixture",
        "classification_status": "INFERRED",
        "evidence_id": evidence_id,
    }
    db.add(
        ClassificationEvidenceRecord(
            id=evidence_id,
            image_asset_id=asset_id,
            inventory_revision_id=None,
            evidence_packet={"devices": [candidate]},
            provider="fixture-vision",
            pipeline_version="vision-v1",
            status="INFERRED",
            created_at=now,
        )
    )
    db.commit()


def _post_resolution(db_session, rack_id: int, evidence_id: str, idempotency_key: str):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        from tests.conftest import rack_owner_headers

        return TestClient(app).post(
            f"/api/racks/{rack_id}/evidence/decision-resolution",
            json={"evidence_id": evidence_id, "idempotency_key": idempotency_key},
            headers=rack_owner_headers(db_session, rack_id),
        )
    finally:
        app.dependency_overrides.clear()


def test_route_flag_on_builds_loader_and_sends_image(
    db_session, sample_rack_basic, tmp_path, monkeypatch
) -> None:
    import evidence.routes as routes

    evidence_id = "ev-vis-route"
    asset_id = "img-vis-route"
    _seed_api_evidence(
        db_session,
        sample_rack_basic,
        evidence_id=evidence_id,
        asset_id=asset_id,
        storage_root=tmp_path / "evidence",
    )

    calls: list[dict] = []
    captured: dict[str, Any] = {}

    def factory(*, image_loader=None):
        assert isinstance(image_loader, BoundEvidenceImageLoader)
        captured["loader"] = image_loader
        return _mock_provider(
            _recording_handler(calls, choice="module-a", confidence=0.95),
            image_loader=image_loader,
        )

    monkeypatch.setattr(routes, "_configured_decision_provider", factory)
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    monkeypatch.setattr(settings, "decision_provider", "clef")
    monkeypatch.setattr(settings, "enable_clef_provider", True)
    monkeypatch.setattr(settings, "export_dir", str(tmp_path))

    response = _post_resolution(db_session, sample_rack_basic.id, evidence_id, "clef-vis-on")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "clef"
    assert body["canonical_authority"] is False
    assert body["selected_choice"] == "module-a"

    assert len(calls) == 1
    assert len(calls[0]["images"]) == 1
    assert captured["loader"].load_count == 1
    assert captured["loader"].last_decision is ImageAccessDecision.CLEARED

    assert db_session.query(DecisionReceiptRecord).count() == 1
    assert db_session.query(SystemInventoryRevisionRecord).count() == 0


def test_route_flag_off_never_builds_loader_or_calls_network(
    db_session, sample_rack_basic, tmp_path, monkeypatch
) -> None:

    evidence_id = "ev-vis-off"
    _seed_api_evidence(
        db_session,
        sample_rack_basic,
        evidence_id=evidence_id,
        asset_id="img-vis-off",
        storage_root=tmp_path / "evidence",
    )

    def exploding_init(self, *args, **kwargs):
        raise AssertionError("the loader must not be constructed while the flag is off")

    monkeypatch.setattr(BoundEvidenceImageLoader, "__init__", exploding_init)

    def exploding_post(self, *args, **kwargs):
        raise AssertionError("no network call is permitted while the flag is off")

    # Patch the adapter's only network method (patching httpx.Client.post would also
    # intercept the FastAPI TestClient, which subclasses httpx.Client).
    monkeypatch.setattr(ClefDecisionProvider, "_post", exploding_post)

    monkeypatch.setattr(settings, "enable_decision_intelligence", True)
    monkeypatch.setattr(settings, "decision_provider", "clef")
    monkeypatch.setattr(settings, "enable_clef_provider", False)
    monkeypatch.setattr(settings, "export_dir", str(tmp_path))

    response = _post_resolution(db_session, sample_rack_basic.id, evidence_id, "clef-vis-off")

    assert response.status_code == 409
    assert response.json()["detail"] == "CLEF_DISABLED"
    assert db_session.query(DecisionReceiptRecord).count() == 0


# ---------------------------------------------------------------------------
# (10) The real factory forwards the loader
# ---------------------------------------------------------------------------


def test_real_factory_forwards_image_loader(monkeypatch) -> None:
    import evidence.routes as routes

    monkeypatch.setattr(settings, "decision_provider", "clef")
    monkeypatch.setattr(settings, "enable_clef_provider", True)
    monkeypatch.setattr(settings, "cloudflare_account_id", "acct-test")
    monkeypatch.setattr(settings, "cloudflare_ai_api_token", "tok-test")

    def sentinel(request):
        return ()

    provider = routes._configured_decision_provider(image_loader=sentinel)

    assert isinstance(provider, ClefDecisionProvider)
    assert provider._image_loader is sentinel

    unbound = routes._configured_decision_provider()

    assert isinstance(unbound, ClefDecisionProvider)
    assert unbound._image_loader is None
