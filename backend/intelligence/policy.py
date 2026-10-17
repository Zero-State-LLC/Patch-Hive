"""Pure deterministic disposition policy for non-canonical decision packets."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from intelligence.contracts import DecisionPacket


class DecisionDisposition(str, Enum):
    AUTO_PROPOSE = "AUTO_PROPOSE"
    USER_REVIEW = "USER_REVIEW"
    UNRESOLVED = "UNRESOLVED"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"


class PolicyThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str = Field(min_length=1)
    auto_propose_at: float = Field(ge=0, le=1)
    user_review_at: float = Field(ge=0, le=1)
    probability_margin: float = Field(default=0.0, ge=0, lt=0.5)

    def model_post_init(self, __context: object) -> None:
        if self.user_review_at > self.auto_propose_at:
            raise ValueError("user_review_at must be <= auto_propose_at")


class PolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str
    disposition: DecisionDisposition
    reason_codes: tuple[str, ...]
    # Populated only for probability decisions whose direction is sufficiently clear.
    # Disposition expresses confidence/action; binary_conclusion preserves yes/no meaning.
    binary_conclusion: bool | None = None


class DecisionPolicy:
    """No I/O, provider calls, or canonical writes are allowed here."""

    def __init__(self, thresholds: PolicyThresholds) -> None:
        self.thresholds = thresholds

    def evaluate(self, packet: DecisionPacket) -> PolicyResult:
        binary_conclusion: bool | None = None
        if packet.schema_version != "patchhive.decision.v1":
            return self._result(DecisionDisposition.REJECT, "UNSUPPORTED_SCHEMA")

        if packet.provider_status in {"failed", "timed_out"}:
            return self._result(DecisionDisposition.ESCALATE, f"PROVIDER_{packet.provider_status.upper()}")

        if packet.answer_type == "choice":
            if packet.selected_choice in {"none_of_above", "unknown"}:
                return self._result(DecisionDisposition.UNRESOLVED, "ABSTAINED_UNKNOWN")
            certainty = packet.confidence
            if certainty is None and packet.selected_choice is not None:
                certainty = packet.probabilities.get(packet.selected_choice)
        elif packet.answer_type == "score":
            certainty = packet.confidence
        else:
            assert packet.probability_yes is not None
            certainty = max(packet.probability_yes, 1.0 - packet.probability_yes)
            if certainty < 0.5 + self.thresholds.probability_margin:
                return self._result(DecisionDisposition.UNRESOLVED, "PROBABILITY_AMBIGUOUS")
            binary_conclusion = packet.probability_yes >= 0.5

        if certainty is None:
            return self._result(DecisionDisposition.UNRESOLVED, "NO_CONFIDENCE_SIGNAL")
        if certainty >= self.thresholds.auto_propose_at:
            return self._result(DecisionDisposition.AUTO_PROPOSE, "CONFIDENCE_AUTO_PROPOSE", binary_conclusion=binary_conclusion)
        if certainty >= self.thresholds.user_review_at:
            return self._result(DecisionDisposition.USER_REVIEW, "CONFIDENCE_REVIEW", binary_conclusion=binary_conclusion)
        return self._result(DecisionDisposition.UNRESOLVED, "CONFIDENCE_LOW", binary_conclusion=binary_conclusion)

    def _result(
        self,
        disposition: DecisionDisposition,
        reason: str,
        *,
        binary_conclusion: bool | None = None,
    ) -> PolicyResult:
        return PolicyResult(
            policy_version=self.thresholds.policy_version,
            disposition=disposition,
            reason_codes=(reason,),
            binary_conclusion=binary_conclusion,
        )
