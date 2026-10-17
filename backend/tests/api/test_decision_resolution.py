"""API contract for bounded Decision Intelligence resolution."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from canon.models import ClassificationEvidenceRecord, ImageAssetRecord, SystemInventoryRevisionRecord
from core import get_db, settings
from intelligence.contracts import DecisionPacket
from intelligence.models import DecisionReceiptRecord
from main import app


def test_decision_resolution_endpoint_is_advisory_only(db_session, sample_rack_basic, monkeypatch):
    now = datetime.now(timezone.utc)
    asset = ImageAssetRecord(
        id="img-di-api", rack_id=sample_rack_basic.id, user_id=sample_rack_basic.user_id,
        content_sha256="a" * 64, media_type="image/jpeg", width=100, height=100,
        byte_length=10, storage_path="/tmp/di.jpg", retention_days=30,
        retention_expires_at=now + timedelta(days=30), consent_provider_processing=False,
        created_at=now,
    )
    db_session.add(asset)
    candidate = {
        "candidate_id": "module-a", "entity_type": "module", "manufacturer": "Make",
        "model": "Alpha", "confidence": 0.8, "confidence_method": "fixture",
        "classification_status": "INFERRED", "evidence_id": "ev-di-api",
    }
    db_session.add(ClassificationEvidenceRecord(
        id="ev-di-api", image_asset_id=asset.id, inventory_revision_id=None,
        evidence_packet={"devices": [candidate]}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db_session.commit()

    class Provider:
        def choose(self, request):
            return DecisionPacket(
                decision_id="decision-api", request_id=request.request_id,
                provider="fixture", provider_version="1", evidence_hash=request.evidence_hash,
                answer_type="choice", selected_choice="module-a",
                probabilities={"module-a": 0.95, "none_of_above": 0.05},
                confidence=0.95, candidate_set_hash=request.candidate_set_hash(),
                created_at=now,
            )
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError

    import evidence.routes as routes
    monkeypatch.setattr(routes, "_configured_decision_provider", lambda: Provider())
    monkeypatch.setattr(settings, "enable_decision_intelligence", True)

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        before = db_session.query(SystemInventoryRevisionRecord).count()
        response = client.post(
            f"/api/racks/{sample_rack_basic.id}/evidence/decision-resolution",
            json={"evidence_id": "ev-di-api", "idempotency_key": "api-test"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["selected_choice"] == "module-a"
        assert body["disposition"] == "AUTO_PROPOSE"
        assert body["canonical_authority"] is False
        assert db_session.query(DecisionReceiptRecord).count() == 1
        assert db_session.query(SystemInventoryRevisionRecord).count() == before

        listed = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/candidates")
        shown = next(x for x in listed.json()["candidates"] if x["candidate_id"] == "module-a")
        assert shown["decision_advisory"]["provider"] == "fixture"
    finally:
        app.dependency_overrides.clear()
        monkeypatch.setattr(settings, "enable_decision_intelligence", False)


def test_decision_resolution_endpoint_defaults_off(db_session, sample_rack_basic, monkeypatch):
    now = datetime.now(timezone.utc)
    asset = ImageAssetRecord(
        id="img-di-off", rack_id=sample_rack_basic.id, user_id=sample_rack_basic.user_id,
        content_sha256="b" * 64, media_type="image/jpeg", width=100, height=100,
        byte_length=10, storage_path="/tmp/di-off.jpg", retention_days=30,
        retention_expires_at=now + timedelta(days=30), consent_provider_processing=False,
        created_at=now,
    )
    db_session.add(asset)
    db_session.add(ClassificationEvidenceRecord(
        id="ev-di-off", image_asset_id=asset.id, inventory_revision_id=None,
        evidence_packet={"devices": []}, provider="fixture-vision",
        pipeline_version="vision-v1", status="INFERRED", created_at=now,
    ))
    db_session.commit()

    def provider_must_not_run():
        raise AssertionError("provider construction occurred while feature was disabled")

    import evidence.routes as routes
    monkeypatch.setattr(routes, "_configured_decision_provider", provider_must_not_run)
    monkeypatch.setattr(settings, "enable_decision_intelligence", False)

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post(
            f"/api/racks/{sample_rack_basic.id}/evidence/decision-resolution",
            json={"evidence_id": "ev-di-off", "idempotency_key": "off"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "DECISION_INTELLIGENCE_DISABLED"
        assert db_session.query(DecisionReceiptRecord).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_decision_provider_configuration_defaults_fail_closed() -> None:
    assert settings.decision_provider in {"disabled", "jev"}
    if settings.decision_provider == "disabled":
        import evidence.routes as routes
        try:
            routes._configured_decision_provider()
        except RuntimeError as exc:
            assert str(exc) == "DECISION_PROVIDER_NOT_CONFIGURED"
        else:
            raise AssertionError("disabled provider must fail closed")
