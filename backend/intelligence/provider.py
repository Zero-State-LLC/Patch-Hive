"""Decision-provider protocol.

Adapters may call Jev or another provider, but callers depend only on this protocol.
"""

from __future__ import annotations

from typing import Protocol

from intelligence.contracts import ChoiceRequest, DecisionPacket, ProbabilityRequest, ScoreRequest


class DecisionProvider(Protocol):
    def choose(self, request: ChoiceRequest) -> DecisionPacket: ...

    def score(self, request: ScoreRequest) -> DecisionPacket: ...

    def probability(self, request: ProbabilityRequest) -> DecisionPacket: ...
