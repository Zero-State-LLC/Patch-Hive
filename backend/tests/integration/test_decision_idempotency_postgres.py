"""Concurrent resolutions with one idempotency key (spec 005 T083), on Postgres.

Skipped unless DATABASE_URL is a Postgres URL. Runs in its own schema and drops it.
"""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import main  # noqa: F401  (registers every model on Base.metadata)
from canon.models import ClassificationEvidenceRecord, ImageAssetRecord
from core.database import Base
from intelligence.clef_resolution import resolve_module_identity_guarded
from intelligence.contracts import DecisionPacket
from intelligence.models import DecisionReceiptKeyRecord, DecisionReceiptRecord
from intelligence.policy import DecisionPolicy, PolicyThresholds

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL.startswith("postgresql"), reason="needs a Postgres DATABASE_URL"
)

SCHEMA = "idem_race"


class SlowProvider:
    def __init__(self) -> None:
        self.calls = 0

    def choose(self, request):
        self.calls += 1
        time.sleep(0.4)  # hold the window open so the other request overlaps
        return DecisionPacket(
            decision_id=f"decision-{threading.get_ident()}", request_id=request.request_id,
            provider="fixture", provider_version="1", evidence_hash=request.evidence_hash,
            answer_type="choice", selected_choice="module-a",
            probabilities={"module-a": 0.95, "none_of_above": 0.05}, confidence=0.95,
            candidate_set_hash=request.candidate_set_hash(),
            created_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
        )

    def score(self, request): raise AssertionError
    def probability(self, request): raise AssertionError


def test_overlapping_requests_with_one_key_call_the_provider_once() -> None:
    admin = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
    engine = create_engine(DATABASE_URL).execution_options(
        schema_translate_map={None: SCHEMA}
    )
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        now = datetime.now(timezone.utc)
        with Session() as seed:
            # Seed only the rows under test; the rack/user parents are not needed.
            seed.execute(text("SET session_replication_role = replica"))
            seed.add(ImageAssetRecord(
                id="img-1", rack_id=1, user_id=1, content_sha256="a" * 64,
                media_type="image/jpeg", width=100, height=100, byte_length=10,
                storage_path="/tmp/none", retention_days=30,
                retention_expires_at=now + timedelta(days=30),
                consent_provider_processing=False, created_at=now,
            ))
            seed.flush()
            seed.add(ClassificationEvidenceRecord(
                id="ev-1", image_asset_id="img-1", inventory_revision_id=None,
                evidence_packet={"devices": [{
                    "candidate_id": "module-a", "entity_type": "module",
                    "manufacturer": "Make", "model": "Alpha", "confidence": 0.8,
                    "confidence_method": "fixture", "classification_status": "INFERRED",
                    "evidence_id": "ev-1",
                }]},
                provider="fixture-vision", pipeline_version="vision-v1",
                status="INFERRED", created_at=now,
            ))
            seed.commit()

        provider = SlowProvider()
        policy = DecisionPolicy(PolicyThresholds(
            policy_version="test-v1", auto_propose_at=0.9, user_review_at=0.65,
            probability_margin=0.1,
        ))
        outcomes: list = []
        errors: list = []

        def request() -> None:
            try:
                with Session() as db:
                    result = resolve_module_identity_guarded(
                        db, evidence_id="ev-1", provider=provider, policy=policy,
                        enabled=True, idempotency_key="same",
                        expected_policy_version="test-v1",
                    )
                    db.commit()
                    outcomes.append(result)
            except Exception as exc:  # the bug being guarded against is a 500 here
                errors.append(exc)

        threads = [threading.Thread(target=request) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert provider.calls == 1
        assert sorted(r.replayed_outcome is not None for r in outcomes) == [False, True]
        with Session() as check:
            assert check.query(DecisionReceiptRecord).count() == 1
            assert check.query(DecisionReceiptKeyRecord).count() == 1
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        admin.dispose()
