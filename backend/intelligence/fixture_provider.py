"""Deterministic fixture provider for tests and local development."""

from __future__ import annotations

from datetime import datetime, timezone

from intelligence.contracts import ChoiceRequest, DecisionPacket, ProbabilityRequest, ScoreRequest


class FixtureDecisionProvider:
    """Returns caller-supplied fixture packets keyed by request_id."""

    def __init__(self, fixtures: dict[str, DecisionPacket]) -> None:
        self._fixtures = dict(fixtures)

    def _get(self, request_id: str) -> DecisionPacket:
        try:
            return self._fixtures[request_id]
        except KeyError as exc:
            raise KeyError(f"no decision fixture for request_id={request_id}") from exc

    def choose(self, request: ChoiceRequest) -> DecisionPacket:
        packet = self._get(request.request_id)
        if packet.answer_type != "choice":
            raise ValueError("fixture answer_type does not match choice request")
        if packet.request_id != request.request_id or packet.evidence_hash != request.evidence_hash:
            raise ValueError("fixture packet provenance does not match request")
        if packet.provider_status == "succeeded":
            if packet.candidate_set_hash != request.candidate_set_hash():
                raise ValueError("fixture candidate set does not match request")
            if packet.selected_choice not in {choice.choice_id for choice in request.choices}:
                raise ValueError("fixture choice is outside the server-authored candidate set")
        return packet

    def score(self, request: ScoreRequest) -> DecisionPacket:
        packet = self._get(request.request_id)
        if packet.answer_type != "score":
            raise ValueError("fixture answer_type does not match score request")
        if packet.request_id != request.request_id or packet.evidence_hash != request.evidence_hash:
            raise ValueError("fixture packet provenance does not match request")
        if packet.rubric_hash != request.rubric_hash():
            raise ValueError("fixture rubric does not match request")
        return packet

    def probability(self, request: ProbabilityRequest) -> DecisionPacket:
        packet = self._get(request.request_id)
        if packet.answer_type != "probability":
            raise ValueError("fixture answer_type does not match probability request")
        if packet.request_id != request.request_id or packet.evidence_hash != request.evidence_hash:
            raise ValueError("fixture packet provenance does not match request")
        return packet


def failed_fixture(
    *,
    decision_id: str,
    request_id: str,
    provider_status: str,
    evidence_hash: str,
    error_code: str,
) -> DecisionPacket:
    if provider_status not in {"failed", "timed_out"}:
        raise ValueError("failed_fixture requires failed or timed_out status")
    return DecisionPacket(
        decision_id=decision_id,
        request_id=request_id,
        provider="fixture",
        provider_version="1",
        evidence_hash=evidence_hash,
        answer_type="choice",
        provider_status=provider_status,
        error_code=error_code,
        created_at=datetime.now(timezone.utc),
    )
