from datetime import datetime, timezone

from intelligence.contracts import DecisionPacket
from intelligence.fixture_provider import FixtureDecisionProvider
from intelligence.module_service import CatalogCandidate, ModuleDecisionService
from intelligence.policy import DecisionDisposition, DecisionPolicy, PolicyThresholds


def _policy() -> DecisionPolicy:
    return DecisionPolicy(
        PolicyThresholds(
            policy_version="module-test-v1",
            auto_propose_at=0.9,
            user_review_at=0.65,
            probability_margin=0.1,
        )
    )


def test_identity_candidates_are_deterministic_and_include_abstention() -> None:
    # First construct the exact bounded request with a tiny recording provider.
    class Recorder:
        request = None
        def choose(self, request):
            self.request = request
            return DecisionPacket(
                decision_id="d",
                request_id=request.request_id,
                provider="recorder",
                provider_version="1",
                evidence_hash=request.evidence_hash,
                answer_type="choice",
                selected_choice="none_of_above",
                probabilities={
                    **{item.choice_id: 0.0 for item in request.choices[:-1]},
                    "none_of_above": 1.0,
                },
                confidence=1.0,
                candidate_set_hash=request.candidate_set_hash(),
                created_at=datetime.now(timezone.utc),
            )
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError

    provider = Recorder()
    proposal = ModuleDecisionService(provider, _policy()).rank_identity(
        request_id="r",
        evidence_hash="h",
        evidence_refs=("image-1",),
        normalized_evidence={"ocr": "panel"},
        candidates=(
            CatalogCandidate("z", "Make", "Zed"),
            CatalogCandidate("a", "Make", "Alpha"),
        ),
        idempotency_key="idem",
    )
    assert [c.choice_id for c in proposal.request.choices] == ["a", "z", "none_of_above"]
    assert proposal.policy.disposition is DecisionDisposition.UNRESOLVED


def test_family_unknown_never_becomes_canonical_fact() -> None:
    class Provider:
        def choose(self, request):
            probs = {item.choice_id: 0.0 for item in request.choices}
            probs["unknown"] = 1.0
            return DecisionPacket(
                decision_id="d",
                request_id=request.request_id,
                provider="fixture",
                provider_version="1",
                evidence_hash=request.evidence_hash,
                answer_type="choice",
                selected_choice="unknown",
                probabilities=probs,
                confidence=1.0,
                candidate_set_hash=request.candidate_set_hash(),
                created_at=datetime.now(timezone.utc),
            )
        def score(self, request): raise AssertionError
        def probability(self, request): raise AssertionError

    proposal = ModuleDecisionService(Provider(), _policy()).classify_family(
        request_id="family",
        evidence_hash="h",
        normalized_evidence={"labels": []},
        idempotency_key="idem",
    )
    # The intelligence layer emits only a proposal. No canonical model is constructed.
    assert proposal.packet.selected_choice == "unknown"
    assert not hasattr(proposal, "module_revision")


def test_identity_refuses_empty_candidate_universe() -> None:
    service = ModuleDecisionService(FixtureDecisionProvider({}), _policy())
    try:
        service.rank_identity(
            request_id="r",
            evidence_hash="h",
            evidence_refs=(),
            normalized_evidence={},
            candidates=(),
            idempotency_key="idem",
        )
    except ValueError as exc:
        assert "server-supplied" in str(exc)
    else:
        raise AssertionError("empty candidate universe must fail closed")
