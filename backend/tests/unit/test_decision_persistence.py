from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from intelligence.contracts import ChoiceOption, ChoiceRequest, DecisionPacket, DecisionPurpose
from intelligence.models import DecisionReceiptRecord
from intelligence.module_service import DecisionProposal
from intelligence.persistence import persist_decision_proposal
from intelligence.policy import DecisionDisposition, PolicyResult


def _proposal() -> DecisionProposal:
    request = ChoiceRequest(
        request_id="req-1",
        purpose=DecisionPurpose.module_identity,
        evidence_hash="ev-1",
        evidence_refs=("img-1",),
        context={"ocr": "synthetic"},
        idempotency_key="idem-1",
        question="Which candidate?",
        choices=(
            ChoiceOption(choice_id="module-a"),
            ChoiceOption(choice_id="none_of_above"),
        ),
    )
    packet = DecisionPacket(
        decision_id="decision-1",
        request_id=request.request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="module-a",
        probabilities={"module-a": 0.95, "none_of_above": 0.05},
        confidence=0.95,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime.now(timezone.utc),
    )
    policy = PolicyResult(
        policy_version="policy-v1",
        disposition=DecisionDisposition.AUTO_PROPOSE,
        reason_codes=("CONFIDENCE_AUTO_PROPOSE",),
    )
    return DecisionProposal(request=request, packet=packet, policy=policy)


def test_persist_decision_proposal_is_idempotent_and_evidence_bound() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        first = persist_decision_proposal(db, _proposal())
        second = persist_decision_proposal(db, _proposal())
        assert first.id == second.id
        assert db.query(DecisionReceiptRecord).count() == 1
        assert first.evidence_hash == "ev-1"
        assert first.selected_choice == "module-a"
        assert first.disposition == "AUTO_PROPOSE"
