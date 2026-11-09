"""Jack lists: only a complete list, read twice and proven by quotes, is ever proposed."""

from __future__ import annotations

import importlib.util
import json
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
            _reading(_jack("Gate In", "gate_in")),
            _reading(_jack("Gate In", "gate_in")),
            "no_outputs",
        ),
    ],
)
def test_anything_less_is_rejected_with_its_reason(first, second, reason):
    assert jacks.decide_document(DOC, first, second) == (None, reason)


# --- the run, with the API faked ---


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


def _decide(tmp_path: Path, results: tuple) -> dict:
    _submit(tmp_path, _client())
    jacks.collect(tmp_path, lambda: _client(results=results))
    assert jacks.decide(tmp_path, sample=5) == 0
    return json.loads((tmp_path / "module-jacks.proposal.json").read_text())


GOOD = _reading(_jack("Gate In", "gate_in"), _jack("Out L", "audio_out"))
PARTIAL = _reading(_jack("Gate In", "gate_in"), coverage="partial")


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
