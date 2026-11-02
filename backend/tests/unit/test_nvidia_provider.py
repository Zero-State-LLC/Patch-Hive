"""NVIDIA vision DecisionProvider: wire format, mapping and fail-closed behaviour.

The adapter reuses the Clef adapter machine (spec 006) with ``NVIDIA_*`` codes. No test
calls the network: every request goes through an ``httpx.MockTransport``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from intelligence.clef_provider import ClefAdapterState, ClefProviderError, ClefImage
from intelligence.contracts import (
    ChoiceOption,
    ChoiceRequest,
    DecisionPurpose,
    ProbabilityRequest,
    ScoreRequest,
)
from intelligence.nvidia_provider import (
    DEFAULT_BASE_URL,
    NVIDIA_MODELS,
    NvidiaVisionProvider,
    answer_schema,
)


def _choice_request() -> ChoiceRequest:
    return ChoiceRequest(
        request_id="req-nv",
        purpose=DecisionPurpose.module_identity,
        evidence_hash="evidence",
        idempotency_key="idem-nv",
        context={"ocr": "panel text"},
        question="Which candidate best matches the evidence?",
        choices=(
            ChoiceOption(choice_id="mod-a", description="Candidate A"),
            ChoiceOption(choice_id="mod-b", description="Candidate B"),
            ChoiceOption(choice_id="none_of_above"),
        ),
    )


def _completion(content: Any, *, finish: str = "stop") -> dict:
    text = content if isinstance(content, str) else json.dumps(content)
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": NVIDIA_MODELS[0],
        "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": text}}],
    }


def _provider(handler, *, enabled: bool = True, images=None, **kwargs) -> NvidiaVisionProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    loader = (lambda _request: images) if images is not None else None
    return NvidiaVisionProvider(
        enabled=enabled, api_key="nvapi-test" if enabled else "", client=client, image_loader=loader, **kwargs
    )


def _ok_choice(seen: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(
            200,
            json=_completion(
                {"type": "choice", "choice": "mod-a", "probabilities": {"mod-a": 0.8, "mod-b": 0.15, "none_of_above": 0.05}, "confidence": 0.7}
            ),
        )

    return handler


def test_the_model_list_matches_settings_validation() -> None:
    from core.config import Settings

    for model in NVIDIA_MODELS:
        assert Settings(nvidia_model=model).nvidia_model == model
    with pytest.raises(ValueError):
        Settings(nvidia_model="meta/llama-3.2-90b-vision-instruct")


def test_a_choice_is_sent_as_an_openai_chat_with_images_and_a_candidate_schema() -> None:
    seen: list[httpx.Request] = []
    image = ClefImage(content_type="image/png", data=b"\x89PNG-bytes")
    provider = _provider(_ok_choice(seen), images=[image])

    packet = provider.choose(_choice_request())

    (sent,) = seen
    assert str(sent.url) == f"{DEFAULT_BASE_URL}/chat/completions"
    assert sent.headers["authorization"] == "Bearer nvapi-test"
    body = json.loads(sent.content)
    assert body["model"] == NVIDIA_MODELS[0]
    assert body["temperature"] == 0 and body["chat_template_kwargs"] == {"enable_thinking": False}
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["choice"]["enum"] == ["mod-a", "mod-b", "none_of_above"]
    user = body["messages"][1]["content"]
    assert user[0]["type"] == "text" and "mod-b: Candidate B" in user[0]["text"]
    assert user[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORy1ieXRlcw=="}}

    assert packet.provider == "nvidia"
    assert packet.provider_version == NVIDIA_MODELS[0]
    assert packet.selected_choice == "mod-a"
    assert packet.probabilities == {"mod-a": 0.8, "mod-b": 0.15, "none_of_above": 0.05}
    assert packet.raw_payload_hash
    assert provider.provider_name == "nvidia"
    assert provider.last_state is ClefAdapterState.SUCCESS


def test_score_and_probability_questions_map_to_packets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        kind = json.loads(request.content)["response_format"]["json_schema"]["schema"]["properties"]["type"]["const"]
        answer = {"type": "score", "score": 2, "probabilities": {"2": 0.9, "1": 0.1}} if kind == "score" else {"type": "noul", "noul": 0.3}
        return httpx.Response(200, json=_completion(answer))

    provider = _provider(handler)
    score = provider.score(
        ScoreRequest(request_id="r-s", purpose=DecisionPurpose.capability, evidence_hash="e", idempotency_key="i-s",
                     context={}, question="How strong?", levels=("low", "mid", "high"))
    )
    assert (score.answer_type, score.score) == ("score", 2.0)
    prob = provider.probability(
        ProbabilityRequest(request_id="r-p", purpose=DecisionPurpose.capability, evidence_hash="e", idempotency_key="i-p",
                           context={}, question="Present?", true_criteria="yes", false_criteria="no")
    )
    assert (prob.answer_type, prob.probability_yes) == ("probability", 0.3)


def test_disabled_makes_no_call_and_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("network called while disabled")

    with pytest.raises(ClefProviderError) as exc:
        _provider(handler, enabled=False).choose(_choice_request())
    assert exc.value.code == "NVIDIA_DISABLED"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json=_completion("not json")),
        httpx.Response(200, json=_completion({"type": "choice", "choice": "mod-z", "probabilities": {"mod-z": 1.0}})),
        httpx.Response(200, json=_completion({"type": "choice", "choice": "mod-a", "probabilities": {"mod-a": 0.9}}, finish="length")),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, text="<html>"),
    ],
)
def test_malformed_answers_fail_closed(response) -> None:
    with pytest.raises(ClefProviderError) as exc:
        _provider(lambda request: response).choose(_choice_request())
    assert exc.value.code == "NVIDIA_MALFORMED"


def test_transport_failures_fail_closed() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ClefProviderError) as exc:
        _provider(timeout).choose(_choice_request())
    assert exc.value.code == "NVIDIA_TIMEOUT"
    with pytest.raises(ClefProviderError) as exc:
        _provider(lambda request: httpx.Response(503)).choose(_choice_request())
    assert exc.value.code == "NVIDIA_UNAVAILABLE"
    assert "nvapi-test" not in str(exc.value)


def test_a_failing_image_loader_sends_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("sent without images")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    def broken(_request):
        raise OSError("storage down")

    provider = NvidiaVisionProvider(enabled=True, api_key="k", client=client, image_loader=broken)
    with pytest.raises(ClefProviderError) as exc:
        provider.choose(_choice_request())
    assert exc.value.code == "NVIDIA_UNAVAILABLE"


def test_construction_refuses_unpinned_models_and_missing_keys() -> None:
    with pytest.raises(ValueError):
        NvidiaVisionProvider(model="meta/llama-3.2-90b-vision-instruct")
    with pytest.raises(ValueError):
        NvidiaVisionProvider(enabled=True, api_key="")


def test_the_schema_names_only_the_candidates() -> None:
    schema = answer_schema({"type": "choice", "criteria": {"a": "A", "b": "B"}})
    assert schema["properties"]["choice"]["enum"] == ["a", "b"]
    assert schema["properties"]["probabilities"]["additionalProperties"] is False


def test_clef_still_reports_clef_codes_and_name() -> None:
    from intelligence.clef_provider import ClefDecisionProvider

    clef = ClefDecisionProvider()
    assert clef.provider_name == "clef"
    with pytest.raises(ClefProviderError) as exc:
        clef.choose(_choice_request())
    assert exc.value.code == "CLEF_DISABLED"


def test_the_route_builds_the_nvidia_provider_only_when_configured(monkeypatch) -> None:
    import evidence.routes as routes

    monkeypatch.setattr(routes.settings, "decision_provider", "nvidia")
    monkeypatch.setattr(routes.settings, "enable_nvidia_provider", False)
    provider = routes._configured_decision_provider()
    assert isinstance(provider, NvidiaVisionProvider)
    with pytest.raises(ClefProviderError) as exc:
        provider.choose(_choice_request())
    assert exc.value.code == "NVIDIA_DISABLED"
    assert routes._guarded_failure_status("NVIDIA_DISABLED") == 409

    monkeypatch.setattr(routes.settings, "enable_nvidia_provider", True)
    monkeypatch.setattr(routes.settings, "nvidia_api_key", "")
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY_NOT_CONFIGURED"):
        routes._configured_decision_provider()


def test_production_refuses_the_nvidia_flag() -> None:
    from types import SimpleNamespace

    from core.startup_policy import validate_decision_startup_policy

    with pytest.raises(RuntimeError, match="enable_nvidia_provider"):
        validate_decision_startup_policy(SimpleNamespace(environment="production", enable_nvidia_provider=True))
