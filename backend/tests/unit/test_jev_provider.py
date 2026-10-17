import httpx

from intelligence.contracts import ChoiceOption, ChoiceRequest, DecisionPurpose
from intelligence.jev_provider import JevDecisionProvider


def test_jev_choice_maps_wire_response_without_canonical_authority() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["Idempotency-Key"] == "idem"
        payload = __import__("json").loads(request.content)
        assert payload["model"] == "jev-test"
        assert payload["questions"]["req-jev"]["criteria"]["none_of_above"] is None
        return httpx.Response(
            200,
            json={
                "result": {
                    "answers": {
                        "req-jev": {
                            "type": "choice",
                            "choice": "mod-a",
                            "probabilities": {"mod-a": 0.91, "none_of_above": 0.09},
                            "confidence": 0.91,
                        }
                    }
                }
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = JevDecisionProvider(
        api_key="test-key",
        base_url="https://example.invalid",
        model="jev-test",
        client=client,
    )
    request = ChoiceRequest(
        request_id="req-jev",
        purpose=DecisionPurpose.module_identity,
        evidence_hash="evidence",
        idempotency_key="idem",
        context={"ocr": "Maths-like panel text", "candidate_count": 1},
        question="Which candidate best matches the normalized evidence?",
        choices=(
            ChoiceOption(choice_id="mod-a", description="Candidate A"),
            ChoiceOption(choice_id="none_of_above"),
        ),
    )

    packet = provider.choose(request)
    assert packet.provider == "jev"
    assert packet.selected_choice == "mod-a"
    assert packet.candidate_set_hash == request.candidate_set_hash()
    assert not hasattr(packet, "canonical_module_id")



def test_jev_rejects_moving_model_aliases() -> None:
    import pytest

    for model in ("", "jev-latest", "jev-preview", "vendor-latest"):
        with pytest.raises(ValueError, match="model|moving aliases"):
            JevDecisionProvider(api_key="test-key", model=model)


def test_jev_timeout_maps_to_stable_provider_error() -> None:
    import pytest
    from intelligence.jev_provider import JevProviderError

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = JevDecisionProvider(api_key="test-key", model="jev-2026-09-25", client=client)
    request = ChoiceRequest(
        request_id="req-timeout", purpose=DecisionPurpose.module_identity,
        evidence_hash="ev", idempotency_key="idem-timeout", context={},
        question="Which?", choices=(
            ChoiceOption(choice_id="module-a"), ChoiceOption(choice_id="none_of_above"),
        ),
    )
    with pytest.raises(JevProviderError, match="JEV_TIMEOUT"):
        provider.choose(request)
