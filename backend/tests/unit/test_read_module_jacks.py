"""Jack lists: only a complete list, read twice and proven by quotes, is ever proposed."""

from __future__ import annotations

import importlib.util
import io
import json
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "read_module_jacks.py"
FILLER = "Filler words about the module that pad this page past the minimum length. " * 4


def _load():
    spec = importlib.util.spec_from_file_location("_read_module_jacks", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jacks = _load()


def _jack(name: str, kind: str, quote: str = "Gate In and Out L") -> dict:
    return {"name": name, "type": kind, "type_basis": "stated", "quote": quote}


def _reading(*items: dict, coverage: str = "full") -> dict:
    return {"coverage": coverage, "jacks": list(items), "note": ""}


def _page(title: str, url: str, text: str = "words", **extra) -> dict:
    return {
        "title": title,
        "url": url,
        "text": text,
        "brand": "Maker",
        "product_like": True,
        **extra,
    }


def _stored(url: str, sha: str = "a" * 64) -> dict:
    return {"url": url, "sha256": sha, "kind": "pdf", "manual": True}


# --- which document belongs to which Module ---


def test_a_page_counts_only_when_its_title_or_address_is_the_module():
    wanted = _page("Maths – Make Noise", "https://x/modules/maths/", text="short")
    longer = _page("Maths and more", "https://x/news/", text="a much longer article")
    mention = _page("News about Maths", "https://x/blog/")
    assert jacks.pick_page("Maths", [wanted, mention])["url"] == wanted["url"]
    assert jacks.pick_page("Maths", [wanted, longer])["url"] == longer["url"]
    assert jacks.pick_page("Maths", [mention]) is None


def test_a_longer_name_that_merely_begins_the_same_is_another_product():
    assert jacks.pick_page("LFO", [_page("LFO2 — Maker", "https://x/lfo2")]) is None
    assert jacks.pick_page("Mix", [_page("Mixer", "https://x/mixer")]) is None
    assert jacks.pick_page("LFO", [_page("LFO — Maker", "https://x/a")])["url"] == "https://x/a"


@pytest.mark.parametrize(
    "title", ["TB-EFA Rev2 – Maker", "TB-EFA II", "TB-EFA Mk2 - Maker", "TB-EFA 2"]
)
def test_a_page_for_a_later_version_is_not_this_row(title):
    assert jacks.pick_page("TB-EFA", [_page(title, "https://x/a")]) is None


def test_a_width_after_the_name_is_not_a_version():
    assert jacks.pick_page("LFO", [_page("LFO 8HP", "https://x/a")])["url"] == "https://x/a"


def test_a_micro_sign_is_part_of_the_name():
    assert jacks.norm("\u00b5VCA") == "uvca"
    assert jacks.norm("\u03bcVCA") == "uvca"
    assert jacks.pick_page("VCA", [_page("\u00b5VCA - Maker", "https://x/a")]) is None
    assert (
        jacks.pick_page("\u00b5VCA", [_page("\u00b5VCA - Maker", "https://x/a")])["url"]
        == "https://x/a"
    )


def test_a_page_stating_another_width_is_another_revision():
    assert jacks.width_conflict(12, "TB-EFA Rev2 14hp filter") is True
    assert jacks.width_conflict(14, "TB-EFA Rev2 14hp filter") is False
    assert jacks.width_conflict(12, "no width stated here") is False
    assert jacks.width_conflict(12, "was 12hp, now 14hp") is False


def test_the_user_manual_wins_over_a_build_guide_and_a_translation():
    urls = ["https://x/build-guide.pdf", "https://x/manual-fr.pdf", "https://x/manual.pdf"]
    page = {"pdfs": [{"url": url, "label": "pdf", "manual": True} for url in urls]}
    stored = {url: _stored(url) for url in urls}
    assert jacks.pick_manual(page, stored)["url"] == "https://x/manual.pdf"


def test_a_module_named_like_a_build_word_keeps_its_manual():
    url = "https://x/Pressure-Points-manual.pdf"
    page = {"pdfs": [{"url": url, "label": "Manual"}]}
    assert jacks.pick_manual(page, {url: _stored(url)})["url"] == url


def test_a_manual_the_crawl_could_not_store_is_not_picked():
    page = {"pdfs": [{"url": "https://x/manual.pdf", "label": "Manual", "manual": True}]}
    assert jacks.pick_manual(page, {}) is None


def test_a_tech_card_counts_as_a_manual_and_a_preset_sheet_does_not():
    url, other = "https://x/Osc+Tech+Card.pdf", "https://x/preset-sheets.pdf"
    page = {"pdfs": [{"url": url, "label": "Download"}, {"url": other, "label": "pdf"}]}
    assert jacks.pick_manual(page, {url: _stored(url), other: _stored(other)})["url"] == url


def test_a_manual_that_never_names_the_module_is_another_products():
    assert jacks.names_the_module("Tape-Op Distortion", "T A P E - O P D I S T O R T I O N") is True
    assert jacks.names_the_module("AXON-1", "SQUID SALMPLE user manual") is False
    assert jacks.names_the_module("DVDR: Power-of-two divider", "The DVDR divides clocks") is True


def test_the_plan_skips_rows_it_must_not_fill_and_says_why():
    modules = [
        {"id": 1, "brand": "Maker", "name": "Maths", "hp": 20, "status": "active", "io_ports": []},
        {
            "id": 2,
            "brand": "Maker",
            "name": "Done",
            "status": "active",
            "io_ports": [{"name": "X"}],
        },
        {"id": 3, "brand": "Maker", "name": "Gone", "status": "deprecated", "io_ports": []},
        {"id": 4, "brand": "Maker", "name": "Unseen", "status": "active", "io_ports": []},
        {"id": 5, "brand": "Maker", "name": "Wider", "hp": 2, "status": "active", "io_ports": []},
    ]
    url = "https://x/maths.pdf"
    pages = [
        _page("Maths", "https://x/maths", pdfs=[{"url": url, "label": "Manual", "manual": True}]),
        _page("Wider", "https://x/wider", text="now 8hp"),
    ]
    shards = [{"key": "shards/maker-0001.tar", "sha256": "b" * 64, "files": ["a" * 64]}]
    rows, text, counts = jacks.build_plan(modules, pages, [_stored(url)], shards)
    assert [row["module_id"] for row in rows] == [1]
    assert rows[0]["manual"]["shard"] == "shards/maker-0001.tar"
    assert text == {"1": "words"}
    assert counts["already_has_jacks"] == 1
    assert counts["not_active"] == 1
    assert counts["no_matching_page"] == 1
    assert counts["page_states_another_width"] == 1


# --- the gate ---


def test_a_quote_must_be_in_the_document():
    words = jacks._words("The “Accent” jack input can be used. Diﬀerent wording follows.")
    assert jacks.quote_found("The Accent jack input", words) is True
    assert jacks.quote_found("Different wording", words) is True
    assert jacks.quote_found("The Velocity jack input", words) is False
    assert jacks.quote_found("", words) is False


def test_a_quote_survives_pdf_text_coming_out_of_order():
    words = jacks._words("8AUDIO OUTPUT\nCV input R is normaled to CV input L.\nOutput of the VCA.")
    assert jacks.quote_found("AUDIO OUTPUT Output of the VCA.", words) is True


def test_two_readings_may_word_a_jack_differently():
    first = [_jack("Rate CV input", "cv_in"), _jack("Out L", "audio_out")]
    second = [_jack("Left output", "audio_out"), _jack("Rate CV", "cv_in")]
    assert jacks.lists_agree(first, second) is None


def test_a_longer_name_for_the_same_jack_still_agrees():
    first = [_jack("Variable Pulse Width Output", "audio_out")]
    assert jacks.lists_agree(first, [_jack("Pulse Output", "audio_out")]) is None


def test_gate_and_clock_are_one_signal():
    assert jacks.lists_agree([_jack("Clock", "clock_in")], [_jack("Clock", "gate_in")]) is None


def test_readings_disagree_on_direction_signal_name_or_count():
    one = [_jack("Mix", "audio_out")]
    assert jacks.lists_agree(one, [_jack("Mix", "audio_in")]) == "different_type"
    assert jacks.lists_agree(one, [_jack("Mix", "cv_out")]) == "different_type"
    assert jacks.lists_agree(one, [_jack("Sonar", "audio_out")]) == "different_names"
    assert jacks.lists_agree(one, one + [_jack("Sonar", "audio_out")]) == "different_count"


def test_exact_names_pair_up_before_looser_ones():
    first = [_jack("CV", "cv_in"), _jack("Rate CV", "cv_in")]
    second = [_jack("Rate CV", "cv_in"), _jack("CV", "cv_in")]
    assert jacks.lists_agree(first, second) is None


DOC = "The panel has Gate In and Out L for patching."


def test_both_readings_complete_and_agreeing_is_accepted():
    one = _reading(_jack("Gate In", "gate_in"), _jack("Out L", "audio_out"))
    two = _reading(_jack("Out L", "audio_out"), _jack("Gate", "gate_in"))
    accepted, reason = jacks.decide_document(DOC, one, two)
    assert reason == "accepted"
    assert [j["name"] for j in accepted] == ["Gate In", "Out L"]


@pytest.mark.parametrize(
    ("first", "second", "reason"),
    [
        (None, _reading(_jack("Gate In", "gate_in")), "reading_missing"),
        (
            _reading(_jack("Gate In", "gate_in"), coverage="partial"),
            _reading(_jack("Gate In", "gate_in")),
            "not_complete",
        ),
        (_reading(), _reading(), "no_jacks"),
        (
            _reading(_jack("Reset", "gate_in", quote="a Reset socket on top")),
            _reading(_jack("Reset", "gate_in")),
            "quote_not_in_document",
        ),
        (
            _reading(_jack("Gate In", "gate_in"), _jack("Gate In", "gate_in")),
            _reading(_jack("Gate In", "gate_in"), _jack("Gate In", "gate_in")),
            "duplicate_names",
        ),
        (
            _reading(_jack("Out 1", "audio_out"), _jack("Out 2", "audio_out")),
            _reading(_jack("Out", "audio_out"), _jack("Out", "audio_out")),
            "duplicate_names",
        ),
        (
            _reading(_jack("Gate In", "gate_in")),
            _reading(_jack("Gate In", "gate_in")),
            "no_outputs",
        ),
    ],
)
def test_anything_less_is_rejected_with_its_reason(first, second, reason):
    assert jacks.decide_document(DOC, first, second) == (None, reason)


def test_one_channel_of_a_dual_module_is_not_a_complete_list():
    doc = "A dual channel gate. Gate In and Out L. Use channel 2 the same way."
    one = _reading(_jack("Gate In", "gate_in"), _jack("Output", "audio_out"))
    assert jacks.decide_document(doc, one, one) == (None, "one_channel_of_many")


def test_a_dual_module_with_each_channel_listed_is_accepted():
    doc = "A dual channel gate. Gate In and Out L. Use channel 2 the same way."
    one = _reading(
        _jack("Gate In 1", "gate_in"),
        _jack("Out 1", "audio_out"),
        _jack("Gate In 2", "gate_in"),
        _jack("Out 2", "audio_out"),
    )
    assert jacks.decide_document(doc, one, one)[1] == "accepted"


def test_two_of_a_modules_own_parts_means_one_list_is_not_complete():
    doc = "Decay\nTwo voltage controlled decay envelopes.\nGate In and Out L"
    one = _reading(_jack("Gate In", "gate_in"), _jack("Output", "audio_out"))
    assert jacks.decide_document(doc, one, one) == (None, "one_channel_of_many")


def test_an_advert_further_down_is_not_the_modules_own_description():
    doc = "One envelope. Gate In and Out L." + " " * 900 + "Pair it with our dual VCA."
    one = _reading(_jack("Gate In", "gate_in"), _jack("Output", "audio_out"))
    assert jacks.decide_document(doc, one, one)[1] == "accepted"


def test_a_list_for_a_single_channel_module_needs_no_channel_marks():
    one = _reading(_jack("Gate In", "gate_in"), _jack("Output", "audio_out"))
    assert jacks.decide_document("Gate In and Out L", one, one)[1] == "accepted"


# --- the run, with the API faked ---


def test_a_relative_out_folder_downloads_to_the_right_place(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, cwd=kwargs["cwd"])
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(jacks.subprocess, "run", run)
    jacks._fetch_shard("shards/a.tar", Path("RUN/pdf/a.tar"), "bucket", Path("edge/api"))
    command = seen["command"]
    assert command[command.index("--file") + 1] == str((tmp_path / "RUN/pdf/a.tar").resolve())
    assert command[0] == str((tmp_path / "edge/api/node_modules/.bin/wrangler").resolve())
    assert seen["cwd"] == (tmp_path / "edge/api").resolve()


def _plan(out: Path, *, manual: bool = True) -> dict:
    (out / "docs").mkdir(parents=True)
    (out / "text").mkdir()
    row = {
        "module_id": 7,
        "brand": "Maker",
        "name": "Maths",
        "hp": 20,
        "page_url": "https://x/maths",
        "manual": (
            {"url": "https://x/m.pdf", "sha256": "c" * 64, "shard": "s", "shard_sha256": "d"}
            if manual
            else None
        ),
    }
    (out / "plan.json").write_text(json.dumps([row]))
    (out / "docs" / "7-page.txt").write_text(f"Maths has Gate In and Out L. {FILLER}")
    (out / "text" / f"{'c' * 64}.txt").write_text(f"Maths manual: Gate In and Out L. {FILLER}")
    return row


def _client(status: str = "ended", results: tuple = ()) -> SimpleNamespace:
    calls: list = []

    def create(requests):
        calls.append(requests)
        return SimpleNamespace(id="batch_1")

    batches = SimpleNamespace(
        create=create,
        retrieve=lambda _id: SimpleNamespace(processing_status=status, request_counts="counts"),
        results=lambda _id: iter(results),
    )
    return SimpleNamespace(messages=SimpleNamespace(batches=batches), calls=calls)


def _result(key: str, reading: dict | None, *, stop: str = "end_turn") -> SimpleNamespace:
    text = "not json" if reading is None else json.dumps(reading)
    message = SimpleNamespace(
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
    )
    return SimpleNamespace(custom_id=key, result=SimpleNamespace(type="succeeded", message=message))


def _submit(out: Path, api, *, max_usd: float | None = 5.0, dry_run: bool = False) -> int:
    return jacks.submit(
        out, model=jacks.MODEL, max_usd=max_usd, limit=None, dry_run=dry_run, client=lambda: api
    )


def test_every_document_is_read_twice_with_no_tools_and_the_document_between_markers(tmp_path):
    _plan(tmp_path)
    api = _client()
    assert _submit(tmp_path, api) == 0
    requests = api.calls[0]
    assert sorted(r["custom_id"] for r in requests) == [
        "m7-manual-a",
        "m7-manual-b",
        "m7-page-a",
        "m7-page-b",
    ]
    params = requests[0]["params"]
    assert params["model"] == "claude-haiku-5-5"
    assert "tools" not in params
    assert params["output_config"]["effort"] == "low"
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert "--- DOCUMENT START ---\nMaths manual" in params["messages"][0]["content"]
    assert requests[0]["params"]["system"] != requests[1]["params"]["system"]


def test_a_dry_run_spends_nothing(tmp_path, capsys):
    _plan(tmp_path)
    api = _client()
    assert _submit(tmp_path, api, max_usd=None, dry_run=True) == 0
    assert api.calls == []
    assert "requests: 4" in capsys.readouterr().out


@pytest.mark.parametrize("cap", [None, 0.00001])
def test_no_cap_or_too_low_a_cap_is_refused(tmp_path, cap):
    _plan(tmp_path)
    api = _client()
    with pytest.raises(jacks.Refused) as refused:
        _submit(tmp_path, api, max_usd=cap)
    assert refused.value.code == "OVER_BUDGET"
    assert api.calls == []


def test_a_second_submit_waits_for_the_first_to_be_collected(tmp_path):
    _plan(tmp_path)
    api = _client()
    _submit(tmp_path, api)
    with pytest.raises(jacks.Refused) as refused:
        _submit(tmp_path, api)
    assert refused.value.code == "BATCH_NOT_COLLECTED"
    assert len(api.calls) == 1


def test_an_unfinished_batch_collects_nothing(tmp_path):
    _plan(tmp_path)
    _submit(tmp_path, _client())
    assert jacks.collect(tmp_path, lambda: _client(status="in_progress")) == 3
    assert (tmp_path / "pending.json").exists()
    assert not (tmp_path / "readings.jsonl").exists()


def test_only_reads_that_failed_are_paid_for_again(tmp_path):
    _plan(tmp_path, manual=False)
    good = _reading(_jack("Gate In", "gate_in"))
    _submit(tmp_path, _client())
    done = _client(results=(_result("m7-page-a", good), _result("m7-page-b", None)))
    assert jacks.collect(tmp_path, lambda: done) == 0
    again = _client()
    _submit(tmp_path, again)
    assert [r["custom_id"] for r in again.calls[0]] == ["m7-page-b"]


def test_a_cut_off_answer_is_not_a_reading(tmp_path):
    _plan(tmp_path, manual=False)
    good = _reading(_jack("Gate In", "gate_in"))
    _submit(tmp_path, _client())
    done = _client(results=(_result("m7-page-a", good, stop="max_tokens"),))
    jacks.collect(tmp_path, lambda: done)
    assert jacks.load_readings(tmp_path)["m7-page-a"]["reading"] is None


def test_collect_records_what_the_batch_cost(tmp_path):
    _plan(tmp_path, manual=False)
    good = _reading(_jack("Gate In", "gate_in"))
    _submit(tmp_path, _client())
    jacks.collect(tmp_path, lambda: _client(results=(_result("m7-page-a", good),)))
    spend = json.loads((tmp_path / "spend.jsonl").read_text())
    assert spend["tokens"] == [1000, 200]
    assert spend["usd"] == pytest.approx((1000 * 0.10 + 200 * 0.50) / 1e6 * 0.5, abs=1e-4)


GOOD = _reading(_jack("Gate In", "gate_in"), _jack("Out L", "audio_out"))
PARTIAL = _reading(_jack("Gate In", "gate_in"), coverage="partial")


# --- the run through OpenRouter, with the network faked ---


def _answer(reading: dict | None, *, finish: str = "stop", cost: float | None = 0.001) -> dict:
    usage = {"prompt_tokens": 1000, "completion_tokens": 200}
    if cost is not None:
        usage["cost"] = cost
    content = "not json" if reading is None else json.dumps(reading)
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}], "usage": usage}


def _read(out: Path, call, *, max_usd: float | None = 5.0, dry_run: bool = False) -> int:
    return jacks.read_documents(
        out,
        model=jacks.OPENROUTER_MODEL,
        max_usd=max_usd,
        limit=None,
        dry_run=dry_run,
        call=call,
        workers=1,
        pause=lambda _seconds: None,
    )


def _recording(answer):
    calls: list = []

    def call(body):
        calls.append(body)
        return answer(body) if callable(answer) else answer

    return call, calls


def test_an_openrouter_request_keeps_the_schema_and_asks_for_its_cost(tmp_path):
    _plan(tmp_path, manual=False)
    call, calls = _recording(_answer(GOOD))
    assert _read(tmp_path, call) == 0
    body = calls[0]
    assert body["model"] == "anthropic/claude-haiku-5.5"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert "--- DOCUMENT START ---" in body["messages"][1]["content"]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == jacks.READING_SCHEMA
    assert body["provider"] == {"require_parameters": True}
    assert body["usage"] == {"include": True}
    assert body["reasoning"] == {"effort": "low"}
    assert "tools" not in body


def test_a_dry_read_spends_nothing(tmp_path, capsys):
    _plan(tmp_path)
    call, calls = _recording(_answer(GOOD))
    assert _read(tmp_path, call, max_usd=None, dry_run=True) == 0
    assert calls == []
    assert "requests: 4" in capsys.readouterr().out


@pytest.mark.parametrize("cap", [None, 0.00001])
def test_reading_without_a_big_enough_cap_is_refused(tmp_path, cap):
    _plan(tmp_path)
    call, calls = _recording(_answer(GOOD))
    with pytest.raises(jacks.Refused) as refused:
        _read(tmp_path, call, max_usd=cap)
    assert refused.value.code == "OVER_BUDGET"
    assert calls == []


def test_openrouter_readings_reach_the_gate_and_their_cost_is_recorded(tmp_path):
    _plan(tmp_path, manual=False)
    call, _calls = _recording(_answer(GOOD, cost=0.002))
    assert _read(tmp_path, call) == 0
    spend = json.loads((tmp_path / "spend.jsonl").read_text())
    assert spend["provider"] == "openrouter"
    assert spend["requests"] == 2
    assert spend["tokens"] == [2000, 400]
    assert spend["usd"] == pytest.approx(0.004)
    assert jacks.decide(tmp_path, sample=5) == 0
    proposal = json.loads((tmp_path / "module-jacks.proposal.json").read_text())
    assert proposal["modules"][0]["module_id"] == 7


def test_the_list_price_counts_when_openrouter_reports_no_cost(tmp_path):
    _plan(tmp_path, manual=False)
    call, _calls = _recording(_answer(GOOD, cost=None))
    _read(tmp_path, call)
    expected = 2 * (1000 * 0.10 + 200 * 0.50) / 1e6
    assert json.loads((tmp_path / "spend.jsonl").read_text())["usd"] == pytest.approx(
        expected, abs=1e-4
    )


def test_requests_in_flight_cannot_carry_spending_past_the_cap(tmp_path, capsys):
    row = _plan(tmp_path)
    requests, _counts = jacks.build_requests([row], tmp_path, jacks.OPENROUTER_MODEL)
    hold = max(jacks.largest_charge(r, jacks.OPENROUTER_MODEL) for r in requests)
    cap = hold * 2.5

    def answer(_body):
        time.sleep(0.05)  # Every worker has tried to send before any charge comes back.
        return _answer(GOOD, cost=hold)

    call, calls = _recording(answer)
    result = jacks.read_documents(
        tmp_path,
        model=jacks.OPENROUTER_MODEL,
        max_usd=cap,
        limit=None,
        dry_run=False,
        call=call,
        workers=4,
        pause=lambda _seconds: None,
    )
    assert result == 3
    assert len(calls) == 2
    assert json.loads((tmp_path / "spend.jsonl").read_text())["usd"] <= cap
    assert "2 requests unsent" in capsys.readouterr().out


def test_reading_stops_when_real_charges_reach_the_cap(tmp_path, capsys):
    _plan(tmp_path)
    call, calls = _recording(_answer(GOOD, cost=0.6))
    assert _read(tmp_path, call, max_usd=1.0) == 3
    assert len(calls) == 2
    assert "2 requests unsent" in capsys.readouterr().out


@pytest.mark.parametrize("status", [401, 402, 403])
def test_a_rejected_key_or_empty_account_stops_the_run_at_once(tmp_path, status):
    _plan(tmp_path)

    def answer(_body):
        raise jacks.HttpFailure(status, "API key expired.")

    call, calls = _recording(answer)
    with pytest.raises(jacks.Refused) as refused:
        _read(tmp_path, call)
    assert refused.value.code == "OPENROUTER_REFUSED"
    assert len(calls) == 1
    assert json.loads((tmp_path / "spend.jsonl").read_text())["usd"] == 0


def test_a_rate_limit_is_retried(tmp_path):
    _plan(tmp_path, manual=False)
    replies = [jacks.HttpFailure(429, "slow down"), _answer(GOOD), _answer(GOOD)]

    def answer(_body):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    call, calls = _recording(answer)
    assert _read(tmp_path, call) == 0
    assert len(calls) == 3
    assert all(r["reading"] for r in jacks.load_readings(tmp_path).values())


def test_a_request_that_keeps_failing_is_paid_for_only_when_it_succeeds(tmp_path):
    _plan(tmp_path, manual=False)
    seen = []

    def answer(body):
        seen.append(body["messages"][0]["content"])
        if body["messages"][0]["content"] == jacks.PROMPTS["b"]:
            raise jacks.HttpFailure(500, "boom")
        return _answer(GOOD)

    call, _calls = _recording(answer)
    assert _read(tmp_path, call) == 0
    readings = jacks.load_readings(tmp_path)
    assert readings["m7-page-a"]["reading"] == GOOD
    assert readings["m7-page-b"]["status"] == "http_500"
    again, more = _recording(_answer(GOOD))
    assert _read(tmp_path, again) == 0
    assert [b["messages"][0]["content"] for b in more] == [jacks.PROMPTS["b"]]


def test_a_cut_off_openrouter_answer_is_not_a_reading(tmp_path):
    _plan(tmp_path, manual=False)
    call, _calls = _recording(_answer(GOOD, finish="length"))
    _read(tmp_path, call)
    assert jacks.load_readings(tmp_path)["m7-page-a"]["reading"] is None


def test_an_unparsable_openrouter_answer_is_not_a_reading(tmp_path):
    _plan(tmp_path, manual=False)
    call, _calls = _recording(_answer(None))
    _read(tmp_path, call)
    record = jacks.load_readings(tmp_path)["m7-page-a"]
    assert record["reading"] is None
    assert record["status"] == "unparsable"


def test_reading_without_a_key_is_refused_but_a_dry_read_is_not(tmp_path, monkeypatch, capsys):
    _plan(tmp_path, manual=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert jacks.main(["read", "--out", str(tmp_path), "--max-usd", "1"]) == 1
    assert "NO_API_KEY" in capsys.readouterr().err
    assert jacks.main(["read", "--out", str(tmp_path), "--dry-run"]) == 0


def test_the_openrouter_call_sends_the_key_and_reports_a_refusal(monkeypatch):
    seen = {}

    def urlopen(request, timeout):
        seen["authorization"] = request.get_header("Authorization")
        seen["url"] = request.full_url
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"API key expired."}')
        )

    monkeypatch.setattr(jacks.urllib.request, "urlopen", urlopen)
    with pytest.raises(jacks.HttpFailure) as failure:
        jacks.post_openrouter({"model": "x"}, "secret-value")
    assert failure.value.status == 401
    assert "secret-value" not in str(failure.value)
    assert seen == {
        "authorization": "Bearer secret-value",
        "url": "https://openrouter.ai/api/v1/chat/completions",
    }


def _decide(tmp_path: Path, results: tuple) -> dict:
    _submit(tmp_path, _client())
    jacks.collect(tmp_path, lambda: _client(results=results))
    assert jacks.decide(tmp_path, sample=5) == 0
    return json.loads((tmp_path / "module-jacks.proposal.json").read_text())


def test_a_complete_manual_is_proposed_with_its_source_and_quotes(tmp_path):
    _plan(tmp_path)
    results = tuple(
        _result(f"m7-{doc}-{reading}", GOOD) for doc in ("manual", "page") for reading in "ab"
    )
    proposal = _decide(tmp_path, results)
    module = proposal["modules"][0]
    assert module["source_kind"] == "manual"
    assert module["source_url"] == "https://x/m.pdf"
    assert module["io_ports"] == [
        {"name": "Gate In", "type": "gate_in"},
        {"name": "Out L", "type": "audio_out"},
    ]
    assert module["evidence"][0]["quote"] == "Gate In and Out L"
    assert "Maker Maths" in (tmp_path / "review-sample.md").read_text()


def test_the_page_is_used_when_the_manual_falls_short(tmp_path):
    _plan(tmp_path)
    results = (
        _result("m7-manual-a", PARTIAL),
        _result("m7-manual-b", PARTIAL),
        _result("m7-page-a", GOOD),
        _result("m7-page-b", GOOD),
    )
    assert _decide(tmp_path, results)["modules"][0]["source_kind"] == "page"


def test_a_module_with_no_complete_list_is_left_out_and_explained(tmp_path):
    _plan(tmp_path, manual=False)
    proposal = _decide(tmp_path, (_result("m7-page-a", PARTIAL), _result("m7-page-b", GOOD)))
    assert proposal["modules"] == []
    assert json.loads((tmp_path / "rejected.json").read_text())[0]["reasons"]["page"] == (
        "not_complete"
    )


def test_the_proposal_hash_is_stable_across_reruns(tmp_path):
    _plan(tmp_path, manual=False)
    results = (_result("m7-page-a", GOOD), _result("m7-page-b", GOOD))
    _decide(tmp_path, results)
    first = (tmp_path / "module-jacks.proposal.json").read_bytes()
    assert jacks.decide(tmp_path, sample=5) == 0
    assert (tmp_path / "module-jacks.proposal.json").read_bytes() == first


@pytest.mark.parametrize(
    ("coverages", "one_full", "reason"),
    [
        (("full", "partial"), True, "accepted"),
        (("partial", "full"), True, "accepted"),
        (("full", "partial"), False, "not_complete"),
        (("partial", "partial"), True, "not_complete"),
    ],
)
def test_one_complete_reading_is_enough_only_when_asked_for(coverages, one_full, reason):
    """Spec 003 FR-041: the two readings must still list the same jacks."""
    text = "Gate In and Out L"
    first, second = (
        _reading(_jack("Gate In", "gate_in"), _jack("Out L", "audio_out"), coverage=c) for c in coverages
    )
    assert jacks.decide_document(text, first, second, one_full=one_full)[1] == reason


def test_one_complete_reading_still_needs_the_same_jacks():
    text = "Gate In and Out L"
    first = _reading(_jack("Gate In", "gate_in"), _jack("Out L", "audio_out"))
    second = _reading(_jack("Gate In", "gate_in"), coverage="partial")
    assert jacks.decide_document(text, first, second, one_full=True) == (None, "different_count")


def test_an_overlay_leaves_out_modules_an_earlier_one_holds(tmp_path):
    module = {"brand": "Maker", "hp": 4, "source_kind": "page", "source_url": "https://maker.test/m"}
    ports = [{"name": "Out", "type": "audio_out"}]
    proposal = {"modules": [{**module, "name": "Old", "io_ports": ports}, {**module, "name": "New", "io_ports": ports}]}
    (tmp_path / "module-jacks.proposal.json").write_text(json.dumps(proposal))
    earlier = tmp_path / "v1.json"
    earlier.write_text(json.dumps({"entries": [{**module, "name": "Old", "io_ports": ports}]}))
    target = tmp_path / "v2.json"
    assert jacks.write_overlay(tmp_path, target, earlier=[earlier]) == 0
    assert [entry["name"] for entry in json.loads(target.read_text())["entries"]] == ["New"]


def _decide_one(text: str, *names_and_types: tuple[str, str]) -> str:
    reading = _reading(*(_jack(name, kind) for name, kind in names_and_types))
    return jacks.decide_document(text, reading, reading)[1]


@pytest.mark.parametrize("name", ["Trigger inputs", "Outputs (OUT)", "FM 1&2 input", "CASCADE EQ/CH OUTPUTS"])
def test_a_name_that_stands_for_several_jacks_is_refused(name):
    assert _decide_one("Gate In and Out L", (name, "gate_in"), ("Out", "audio_out")) == "grouped_names"


@pytest.mark.parametrize("name", ["LP Outputs Left", "CV Inputs: Frequency", "Stereo Inputs L"])
def test_a_plural_before_a_qualifier_is_one_jack(name):
    assert _decide_one("Gate In and Out L", (name, "cv_in"), ("Out", "audio_out")) == "accepted"


@pytest.mark.parametrize(
    ("names", "reason"),
    [
        ((("Input 1", "audio_in"), ("Output 1", "audio_out")), "one_channel_of_many"),
        ((("Input CH1", "audio_in"), ("Output CH1", "audio_out"), ("Output CH2", "audio_out")), "accepted"),
        ((("1 Volt per Octave Input", "cv_in"), ("Sine Output", "audio_out")), "accepted"),
    ],
)
def test_a_dual_modules_list_must_go_past_channel_one(names, reason):
    assert _decide_one("A dual channel module. Gate In and Out L", *names) == reason
