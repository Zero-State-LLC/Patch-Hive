import base64
import json
from typing import Any, Callable

import httpx
import pytest

try:
    from intelligence.provider import DecisionProvider
except ImportError:  # pragma: no cover
    from intelligence.providers import DecisionProvider

from intelligence.clef_provider import (
    ADAPTER_TRANSITIONS,
    ClefAdapterEvent,
    ClefAdapterState,
    ClefDecisionProvider,
    ClefImage,
    ClefProviderError,
    InvalidAdapterTransition,
    adapter_transition,
)
from intelligence.contracts import (
    ChoiceOption,
    ChoiceRequest,
    DecisionPacket,
    DecisionPurpose,
    ProbabilityRequest,
    ScoreRequest,
)


def _choice_request(request_id: str = "req-clef") -> ChoiceRequest:
    return ChoiceRequest(
        request_id=request_id,
        purpose=DecisionPurpose.module_identity,
        evidence_hash="evidence",
        idempotency_key=f"idem-{request_id}",
        context={"ocr": "panel text"},
        question="Which candidate best matches the evidence?",
        choices=(
            ChoiceOption(choice_id="mod-a", description="Candidate A"),
            ChoiceOption(choice_id="mod-b", description="Candidate B"),
            ChoiceOption(choice_id="none_of_above"),
        ),
    )


def _score_request() -> ScoreRequest:
    return ScoreRequest(
        request_id="req-score",
        purpose=DecisionPurpose.capability,
        evidence_hash="evidence-score",
        idempotency_key="idem-score",
        context={},
        question="How strong is the capability evidence?",
        levels=("low", "mid", "high"),
    )


def _probability_request() -> ProbabilityRequest:
    return ProbabilityRequest(
        request_id="req-prob",
        purpose=DecisionPurpose.capability,
        evidence_hash="evidence-prob",
        idempotency_key="idem-prob",
        context={},
        question="Is the capability present?",
        true_criteria="Evidence supports presence.",
        false_criteria="Evidence does not support presence.",
    )


def _choice_response(
    choice: str = "mod-a",
    probabilities: dict[str, float] | None = None,
    confidence: Any = 0.91,
) -> dict[str, Any]:
    if probabilities is None:
        probabilities = {"mod-a": 0.91, "mod-b": 0.05, "none_of_above": 0.04}
    answer: dict[str, Any] = {
        "type": "choice",
        "choice": choice,
        "probabilities": probabilities,
    }
    if confidence is not None:
        answer["confidence"] = confidence
    return {"success": True, "result": {"answers": {"q0": answer}}}


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError("network call must not happen")


def _enabled_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> ClefDecisionProvider:
    options: dict[str, Any] = {
        "enabled": True,
        "account_id": "acct-test",
        "api_token": "tok-test",
        "model": "clef",
        "client": httpx.Client(transport=httpx.MockTransport(handler)),
    }
    options.update(kwargs)
    return ClefDecisionProvider(**options)


def _disabled_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> ClefDecisionProvider:
    options: dict[str, Any] = {
        "client": httpx.Client(transport=httpx.MockTransport(handler)),
    }
    options.update(kwargs)
    return ClefDecisionProvider(**options)


def _assert_error(
    exc_info: Any,
    code: str,
    state: ClefAdapterState | None = None,
) -> ClefProviderError:
    error = exc_info.value
    assert error.code == code
    if state is not None:
        assert error.state is state
    assert error.__cause__ is None
    return error


def test_disabled_flag_defaults_off_and_never_calls_network() -> None:
    assert ClefDecisionProvider().last_state is ClefAdapterState.IDLE
    provider = _disabled_provider(_no_network)
    with pytest.raises(ClefProviderError) as exc_info:
        provider.choose(_choice_request())
    _assert_error(exc_info, "CLEF_DISABLED", ClefAdapterState.IDLE)
    assert provider.last_state is ClefAdapterState.IDLE
    assert provider.state_trace == (ClefAdapterState.IDLE,)


def test_enabled_requires_account_id_and_api_token_without_leaking_token() -> None:
    token = "tok-secret-value"
    with pytest.raises(ValueError) as exc_info:
        ClefDecisionProvider(enabled=True, account_id="", api_token=token)
    assert token not in str(exc_info.value)

    with pytest.raises(ValueError, match="account_id and api_token"):
        ClefDecisionProvider(enabled=True, account_id="acct-test", api_token="")


def test_invalid_model_is_rejected() -> None:
    for model in ("", "clef-latest", "clef-preview", "not-clef"):
        with pytest.raises(ValueError, match="pinned Clef selector"):
            ClefDecisionProvider(model=model)


def test_choice_success_maps_packet_and_wire_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok-test"
        assert request.headers["Idempotency-Key"] == "idem-req-clef"
        assert request.url.path.endswith("/accounts/acct-test/ai/run/@cf/cloudflare/clef")
        payload = json.loads(request.content)
        assert payload["model"] == "clef"
        assert payload["state"] == {"ocr": "panel text"}
        question = payload["questions"]["q0"]
        assert question["type"] == "choice"
        assert question["criteria"]["none_of_above"] is None
        return httpx.Response(200, json=_choice_response())

    provider = _enabled_provider(handler)
    request = _choice_request()
    packet = provider.choose(request)

    assert type(packet) is DecisionPacket
    assert packet.provider == "clef"
    assert packet.provider_version == "@cf/cloudflare/clef"
    assert packet.selected_choice == "mod-a"
    assert packet.candidate_set_hash == request.candidate_set_hash()
    assert packet.raw_payload_hash is not None
    assert provider.last_state is ClefAdapterState.SUCCESS
    assert provider.state_trace == (
        ClefAdapterState.IDLE,
        ClefAdapterState.INVOKING,
        ClefAdapterState.SUCCESS,
        ClefAdapterState.IDLE,
    )


def test_clef_flash_selector_is_pinned_in_url_body_and_version() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(
            "/accounts/acct-test/ai/run/@cf/cloudflare/clef-flash"
        )
        payload = json.loads(request.content)
        assert payload["model"] == "clef-flash"
        return httpx.Response(200, json=_choice_response())

    provider = _enabled_provider(handler, model="clef-flash")
    packet = provider.choose(_choice_request("req-flash"))
    assert packet.provider_version == "@cf/cloudflare/clef-flash"


def test_score_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        question = payload["questions"]["q0"]
        assert question["type"] == "score"
        assert question["criteria"] == ["low", "mid", "high"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "answers": {
                        "q0": {
                            "type": "score",
                            "score": 2.0,
                            "probabilities": {"0": 0.1, "1": 0.2, "2": 0.7},
                            "confidence": 0.8,
                        }
                    }
                },
            },
        )

    request = _score_request()
    packet = _enabled_provider(handler).score(request)
    assert packet.answer_type == "score"
    assert packet.score == 2.0
    assert packet.rubric_hash == request.rubric_hash()
    assert packet.probabilities == {"0": 0.1, "1": 0.2, "2": 0.7}


def test_out_of_range_score_maps_to_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"answers": {"q0": {"type": "score", "score": 3.0}}},
            },
        )

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).score(_score_request())
    _assert_error(exc_info, "CLEF_MALFORMED", ClefAdapterState.MALFORMED)


def test_probability_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        question = payload["questions"]["q0"]
        assert question["type"] == "noul"
        assert question["criteria"]["true"] == "Evidence supports presence."
        assert question["criteria"]["false"] == "Evidence does not support presence."
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"answers": {"q0": {"type": "noul", "noul": 0.73}}},
            },
        )

    packet = _enabled_provider(handler).probability(_probability_request())
    assert packet.answer_type == "probability"
    assert packet.probability_yes == 0.73


def test_timeout_maps_to_timeout_state_and_no_packet() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    provider = _enabled_provider(handler)
    with pytest.raises(ClefProviderError) as exc_info:
        provider.choose(_choice_request())
    _assert_error(exc_info, "CLEF_TIMEOUT", ClefAdapterState.TIMEOUT)
    assert provider.last_state is ClefAdapterState.TIMEOUT
    assert provider.state_trace == (
        ClefAdapterState.IDLE,
        ClefAdapterState.INVOKING,
        ClefAdapterState.TIMEOUT,
        ClefAdapterState.IDLE,
    )


def test_http_503_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_UNAVAILABLE", ClefAdapterState.UNAVAILABLE)


def test_connect_error_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connect", request=request)

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_UNAVAILABLE", ClefAdapterState.UNAVAILABLE)


def test_success_false_maps_to_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "result": {}})

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_MALFORMED", ClefAdapterState.MALFORMED)


def test_choice_outside_candidate_set_maps_to_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _choice_response(
            choice="mod-x",
            probabilities={"mod-a": 0.5, "mod-b": 0.5, "none_of_above": 0.0},
        )
        return httpx.Response(200, json=body)

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_MALFORMED", ClefAdapterState.MALFORMED)


def test_probabilities_not_summing_to_one_maps_to_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _choice_response(
            probabilities={"mod-a": 0.5, "mod-b": 0.2, "none_of_above": 0.2}
        )
        return httpx.Response(200, json=body)

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_MALFORMED", ClefAdapterState.MALFORMED)


def test_bool_confidence_maps_to_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_choice_response(confidence=True))

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_MALFORMED", ClefAdapterState.MALFORMED)


def test_invalid_json_body_maps_to_malformed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(handler).choose(_choice_request())
    _assert_error(exc_info, "CLEF_MALFORMED", ClefAdapterState.MALFORMED)


def test_error_does_not_leak_token_or_chain_transport_error() -> None:
    token = "tok-secret-value"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    provider = _enabled_provider(handler, api_token=token)
    with pytest.raises(ClefProviderError) as exc_info:
        provider.choose(_choice_request())
    assert token not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_image_loader_encodes_data_url_without_packet_leak() -> None:
    image_bytes = b"\x89PNG\r\n\x1a\npayload"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    calls: list[str] = []

    def loader(request: Any) -> tuple[ClefImage, ...]:
        calls.append(request.request_id)
        return (ClefImage(content_type="image/png", data=image_bytes),)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["images"] == [f"data:image/png;base64,{encoded}"]
        return httpx.Response(200, json=_choice_response())

    provider = _enabled_provider(handler, image_loader=loader)
    packet = provider.choose(_choice_request())
    assert calls == ["req-clef"]

    dumped = packet.model_dump(mode="json")
    assert "images" not in dumped
    assert encoded not in json.dumps(dumped)


def test_invalid_image_content_type_maps_to_invalid_request_without_network() -> None:
    def loader(request: Any) -> tuple[ClefImage, ...]:
        return (ClefImage(content_type="image/gif", data=b"x"),)

    provider = _enabled_provider(_no_network, image_loader=loader)
    with pytest.raises(ClefProviderError) as exc_info:
        provider.choose(_choice_request())
    _assert_error(exc_info, "CLEF_INVALID_REQUEST", ClefAdapterState.IDLE)


def test_image_loader_not_called_when_disabled() -> None:
    calls: list[Any] = []

    def loader(request: Any) -> tuple[ClefImage, ...]:
        calls.append(request)
        return ()

    provider = _disabled_provider(_no_network, image_loader=loader)
    with pytest.raises(ClefProviderError) as exc_info:
        provider.choose(_choice_request())
    _assert_error(exc_info, "CLEF_DISABLED", ClefAdapterState.IDLE)
    assert calls == []


def test_single_none_of_above_choice_is_rejected_without_network() -> None:
    request = ChoiceRequest(
        request_id="req-one",
        purpose=DecisionPurpose.module_family,
        evidence_hash="ev",
        idempotency_key="idem-one",
        context={},
        question="Which family?",
        choices=(ChoiceOption(choice_id="none_of_above"),),
    )
    with pytest.raises(ClefProviderError) as exc_info:
        _enabled_provider(_no_network).choose(request)
    _assert_error(exc_info, "CLEF_INVALID_REQUEST", ClefAdapterState.IDLE)


def test_adapter_transition_table_and_invalid_pairs() -> None:
    assert adapter_transition(
        ClefAdapterState.IDLE,
        ClefAdapterEvent.INVOKE,
        flag_on=True,
        request_valid=True,
    ) is ClefAdapterState.INVOKING
    assert adapter_transition(
        ClefAdapterState.IDLE,
        ClefAdapterEvent.INVOKE,
        flag_on=False,
        request_valid=True,
    ) is ClefAdapterState.IDLE
    assert adapter_transition(
        ClefAdapterState.IDLE,
        ClefAdapterEvent.INVOKE,
        flag_on=True,
        request_valid=False,
    ) is ClefAdapterState.IDLE

    assert adapter_transition(
        ClefAdapterState.INVOKING,
        ClefAdapterEvent.RESPONSE_OK,
        maps_to_packet=True,
    ) is ClefAdapterState.SUCCESS
    assert adapter_transition(
        ClefAdapterState.INVOKING,
        ClefAdapterEvent.RESPONSE_OK,
        maps_to_packet=False,
    ) is ClefAdapterState.MALFORMED

    assert adapter_transition(
        ClefAdapterState.INVOKING, ClefAdapterEvent.TIMEOUT
    ) is ClefAdapterState.TIMEOUT
    assert adapter_transition(
        ClefAdapterState.INVOKING, ClefAdapterEvent.MALFORMED
    ) is ClefAdapterState.MALFORMED
    assert adapter_transition(
        ClefAdapterState.INVOKING, ClefAdapterEvent.UNAVAILABLE
    ) is ClefAdapterState.UNAVAILABLE
    assert adapter_transition(
        ClefAdapterState.SUCCESS, ClefAdapterEvent.RESET
    ) is ClefAdapterState.IDLE

    assert (ClefAdapterState.IDLE, ClefAdapterEvent.RESET) not in ADAPTER_TRANSITIONS
    with pytest.raises(InvalidAdapterTransition):
        adapter_transition(ClefAdapterState.IDLE, ClefAdapterEvent.RESET)
    with pytest.raises(InvalidAdapterTransition):
        adapter_transition(ClefAdapterState.SUCCESS, ClefAdapterEvent.INVOKE)


def test_no_clef_wire_types_leak_through_public_surface() -> None:
    import intelligence.clef_provider as clef_provider_module

    assert "ClefImage" not in clef_provider_module.__all__


def test_clef_provider_satisfies_decision_provider_protocol() -> None:
    provider: DecisionProvider = ClefDecisionProvider()
    with pytest.raises(ClefProviderError) as exc_info:
        provider.choose(_choice_request())
    _assert_error(exc_info, "CLEF_DISABLED", ClefAdapterState.IDLE)
