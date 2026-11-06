"""Offline tests for scripts/staging/generated_export_check.py.

Each bad page is a real PDF: the engine composes a small pack with the defect, and the check reads
it with the same reader it uses on staging. Nothing here goes over the network.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tomllib
import zipfile
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from canon.compiler import standard_plan_steps
from core.ops.f5_cutover import SeedAccount, runtime_flags_payload
from export.patchbook.design import engine
from export.patchbook.design.content_spine import ModuleDisplay
from export.patchbook.design.engine import compose_design_export_pack
from tests.unit.test_spec_002_compose_stages import DISPLAY, _library, _patch, _recipe

ROOT = Path(__file__).resolve().parents[3]
_spec = spec_from_file_location(
    "generated_export_check", ROOT / "scripts" / "staging" / "generated_export_check.py"
)
assert _spec and _spec.loader
check = module_from_spec(_spec)
sys.modules["generated_export_check"] = check
_spec.loader.exec_module(check)

RUN = "gen-run-1-aaaaaaaaaaaaaaaa"
USER = SeedAccount("golden_demo", "user-pw-for-tests-only", "User")
ADMIN = SeedAccount("admin_demo", "admin-pw-for-tests-only", "Admin")


def _pack(tmp_path: Path, library=None, edit: Callable[[Path], None] | None = None) -> bytes:
    """A small built pack, zipped the way the download route zips it."""
    root = tmp_path / "pack"
    compose_design_export_pack(
        _library() if library is None else library, _recipe(), out_dir=root, export_id="e"
    )
    if edit is not None:
        edit(root)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(root)))
    return buffer.getvalue()


def _read(pack: bytes, run: str = RUN) -> dict[str, Any]:
    return check.check_pack(pack, source_run_id=run)


def _codes(report: dict[str, Any]) -> set[str]:
    return {failure["code"] for failure in report["failures"]}


def _edit_json(path: Path, **fields: Any) -> None:
    path.write_text(json.dumps({**json.loads(path.read_text()), **fields}), encoding="utf-8")


def test_a_good_pack_passes_and_is_counted(tmp_path: Path) -> None:
    report = _read(_pack(tmp_path))
    assert report["status"] == "pass", report["failures"]
    assert report["load_path"] == "generated_patches"
    assert report["counts"] == {
        "pdf_pages": 3,
        "book_pdf_pages": 3,
        "book_manifest_pages": 3,
        "book_page_entries": 3,
        "patches": 1,
        "patch_pages": 1,
        "modules_checked": 3,
        "cables_checked": 2,
        "distinct_operation_texts": 1,
    }
    assert set(report["hashes"]) == {"pack_zip_sha256", "pdf_sha256"}


# --- the export didn't load as generated_patches ------------------------------------


def test_an_export_that_compiled_on_export_fails(tmp_path: Path) -> None:
    report = _read(_pack(tmp_path, replace(_library(), load_path="compile_on_export")))
    assert _codes(report) == {"EXPORT_NOT_GENERATED_PATCHES"}
    assert report["load_path"] == "compile_on_export"


def test_a_load_path_nobody_knows_stays_out_of_the_receipt(tmp_path: Path) -> None:
    pack = _pack(
        tmp_path,
        edit=lambda root: _edit_json(root / "source" / "library_index.json", load_path="surprise"),
    )
    report = _read(pack)
    assert _codes(report) == {"EXPORT_NOT_GENERATED_PATCHES"} and report["load_path"] == "other"


def test_a_pack_from_another_run_fails(tmp_path: Path) -> None:
    assert _codes(_read(_pack(tmp_path), run="gen-run-2-bbbbbbbbbbbbbbbb")) == {
        "EXPORT_NOT_THE_GENERATED_RUN"
    }


# --- the PDF's page count differs from validation/book.json -----------------------


@pytest.mark.parametrize("field", ["pdf_page_count", "manifest_page_count"])
def test_a_page_count_the_receipt_disagrees_with_fails(tmp_path: Path, field: str) -> None:
    pack = _pack(
        tmp_path, edit=lambda root: _edit_json(root / "validation" / "book.json", **{field: 4})
    )
    assert _codes(_read(pack)) == {"PDF_PAGE_COUNT_MISMATCH"}


def _drop_last_page(root: Path) -> None:
    pdf = root / "PatchBook.pdf"
    writer = PdfWriter()
    for page in PdfReader(pdf).pages[:-1]:
        writer.add_page(page)
    with pdf.open("wb") as handle:
        writer.write(handle)


def test_a_pdf_with_a_page_missing_fails(tmp_path: Path) -> None:
    report = _read(_pack(tmp_path, edit=_drop_last_page))
    assert _codes(report) == {"PDF_PAGE_COUNT_MISMATCH"} and report["counts"]["pdf_pages"] == 2


# --- a patch page is missing Construction or Operation ----------------------------


@pytest.mark.parametrize(
    "heading, code",
    [("Construction", "PAGE_MISSING_CONSTRUCTION"), ("Operation", "PAGE_MISSING_OPERATION")],
)
def test_a_page_without_a_required_heading_fails(tmp_path, monkeypatch, heading, code) -> None:
    real = engine.layout_patch_page
    monkeypatch.setattr(
        engine,
        "layout_patch_page",
        lambda *args, **kwargs: [line for line in real(*args, **kwargs) if line.text != heading],
    )
    report = _read(_pack(tmp_path))
    assert code in _codes(report)
    assert {"code": code, "page": 1} in report["failures"]


@pytest.mark.parametrize(
    "function, code",
    [("cable_lines", "PAGE_MISSING_CONSTRUCTION"), ("operation_lines", "PAGE_MISSING_OPERATION")],
)
def test_a_heading_with_nothing_under_it_fails(tmp_path, monkeypatch, function, code) -> None:
    monkeypatch.setattr(engine, function, lambda *args, **kwargs: [])
    assert code in _codes(_read(_pack(tmp_path)))


# --- a page prints a placeholder, a phase tag or padding ---------------------------


@pytest.mark.parametrize(
    "step, code",
    [
        ("Set the level to UNKNOWN.", "PAGE_PRINTS_PLACEHOLDER"),
        ("Set the level to NOT_COMPUTABLE.", "PAGE_PRINTS_PLACEHOLDER"),
        ("[prep] Power down.", "PAGE_PRINTS_PHASE_TAG"),
        ("[threshold] Raise it.", "PAGE_PRINTS_PHASE_TAG"),
        ("[peak] Hold it.", "PAGE_PRINTS_PHASE_TAG"),
        ("[release] Lower it.", "PAGE_PRINTS_PHASE_TAG"),
        ("[seal] Power down.", "PAGE_PRINTS_PHASE_TAG"),
        ("Patch the next cable, verify prior connection, and go on.", "PAGE_PRINTS_PADDING"),
        ("Patch 10:Audio Out:output first.", "PAGE_PRINTS_RAW_PORT_ID"),
    ],
)
def test_a_patch_page_that_prints_this_fails(tmp_path, monkeypatch, step, code) -> None:
    real = engine.operation_lines
    monkeypatch.setattr(engine, "operation_lines", lambda *args: [*real(*args), step])
    report = _read(_pack(tmp_path))
    assert report["failures"] == [{"code": code, "page": 1}]


def test_the_cover_is_read_too(tmp_path: Path) -> None:
    library = replace(_library(), source_run_id="UNKNOWN")
    report = _read(_pack(tmp_path, library), run="UNKNOWN")
    assert report["failures"] == [{"code": "PAGE_PRINTS_PLACEHOLDER", "page": 0}]


@pytest.mark.parametrize(
    "text, code",
    [
        ("Patch 10:Audio\nOut:output first", "PAGE_PRINTS_RAW_PORT_ID"),
        ("then verify prior\nconnection", "PAGE_PRINTS_PADDING"),
        ("  [ prep ]  ", "PAGE_PRINTS_PHASE_TAG"),
        ("", "PAGE_TEXT_EMPTY"),
    ],
)
def test_a_line_break_does_not_hide_it(text: str, code: str) -> None:
    assert check.page_text_failures(text) == [code]


def test_what_a_page_is_allowed_to_print_is_not_flagged() -> None:
    assert not check.page_text_failures(
        "Intent: Rene 2 into Plaits pitch. No audio is patched.\n"
        "1. Make Noise Maths Envelope Out -> Intellijel Polaris CV In [cv]\n"
        "Bring in the CV from Make Noise Maths slowly while monitoring the output.\n"
        "Jack names are generic: the real names aren't on file, so check each panel.\n"
        "patch-789 | execution | cef37a84e02734a6 | recipe:2d4ba57e | eng:0.3.0\n"
    )


def test_the_tags_and_placeholders_are_the_codes_own() -> None:
    assert {f"[{step.phase}]" for step in standard_plan_steps()} == set(check.PHASE_TAGS)
    assert {"", *check.PLACEHOLDERS} == engine.PLACEHOLDERS


# --- a page prints a raw port id ------------------------------------------------------


def test_cables_printed_as_port_ids_fail(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        engine,
        "cable_lines",
        lambda *args: [
            "1. 1:Audio Out:output -> 2:Audio In:input [audio]",
            "2. 3:Envelope Out:output -> 2:CV In:input [cv]",
        ],
    )
    assert {"PAGE_PRINTS_RAW_PORT_ID", "MODULE_NOT_NAMED"} == _codes(_read(_pack(tmp_path)))


# --- a module on the page isn't named by its brand and name -------------------------


def test_cables_that_print_module_ids_fail(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        engine,
        "cable_lines",
        lambda *args: ["1. 1 Audio Out -> 2 Audio In [audio]", "2. 3 Envelope Out -> 2 CV In [cv]"],
    )
    report = _read(_pack(tmp_path))
    # The diagram still names all three. The cables are where the book stopped naming them.
    assert report["failures"] == [{"code": "MODULE_NOT_NAMED", "page": 1, "count": 3}]


def test_a_module_id_from_some_cable_on_fails(tmp_path, monkeypatch) -> None:
    """T091: the seeded run's plan printed a module id from the sixth cable on."""
    monkeypatch.setattr(
        engine,
        "cable_lines",
        lambda *args: [
            "1. Mutable Instruments Plaits Audio Out -> Intellijel Polaris Audio In [audio]",
            "2. 3 Envelope Out -> 2 CV In [cv]",
        ],
    )
    assert _read(_pack(tmp_path))["failures"] == [
        {"code": "MODULE_NOT_NAMED", "page": 1, "count": 2}
    ]


def test_a_cable_that_drops_the_brand_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        engine,
        "cable_lines",
        lambda *args: [
            "1. Plaits Audio Out -> Intellijel Polaris Audio In [audio]",
            "2. Make Noise Maths Envelope Out -> Intellijel Polaris CV In [cv]",
        ],
    )
    assert _codes(_read(_pack(tmp_path))) == {"MODULE_NOT_NAMED"}


@pytest.mark.parametrize("name", ["1", "Plaits", "Module 1"])
def test_page_data_that_does_not_hold_a_brand_and_name_fails(tmp_path, name) -> None:
    """The page prints what its data says, so matching the two isn't enough."""
    library = _library(display={**DISPLAY, "1": ModuleDisplay(name)})
    assert _read(_pack(tmp_path, library))["failures"] == [
        {"code": "MODULE_NOT_NAMED", "page": 1, "count": 1}
    ]


def test_a_module_in_the_page_data_that_the_page_never_prints_fails(tmp_path: Path) -> None:
    def add_module(root: Path) -> None:
        page = root / "pages" / "json" / "page-0001.json"
        modules = {**json.loads(page.read_text())["modules"], "9": "Erica Synths Pico"}
        _edit_json(page, modules=modules)

    assert _read(_pack(tmp_path, edit=add_module))["failures"] == [
        {"code": "MODULE_NOT_NAMED", "page": 1, "count": 1}
    ]


def test_a_long_or_accented_name_that_wraps_still_counts_as_named(tmp_path: Path) -> None:
    display = {
        **DISPLAY,
        "1": ModuleDisplay(
            "Döpfer Musikelektronik Long Brand Name A-110-1 Standard VCO Oscillator"
        ),
        "2": ModuleDisplay(
            "Hyphenated-Brand Extremely Long Module Name With Many Words In It Here"
        ),
    }
    report = _read(_pack(tmp_path, _library(display=display)))
    assert report["status"] == "pass", report["failures"]


def test_a_name_the_fonts_cannot_print_fails(tmp_path: Path) -> None:
    """The book's fonts are WinAnsi, so this page really does print "Instru■ Arbhar"."""
    library = _library(display={**DISPLAY, "1": ModuleDisplay("Instruō Arbhar")})
    assert _read(_pack(tmp_path, library))["failures"] == [
        {"code": "MODULE_NOT_NAMED", "page": 1, "count": 1}
    ]


# --- a pack the check can't read fails; it never passes by reading nothing -----------


def test_bytes_that_are_not_a_zip_fail() -> None:
    assert _codes(_read(b"not a zip")) == {"PACK_UNREADABLE"}


@pytest.mark.parametrize(
    "name", ["source/library_index.json", "validation/book.json", "PatchBook.pdf"]
)
def test_a_missing_file_fails(tmp_path: Path, name: str) -> None:
    report = _read(_pack(tmp_path, edit=lambda root: (root / name).unlink()))
    assert report["failures"] == [{"code": "PACK_FILE_UNREADABLE", "file": name}]


def test_a_damaged_pdf_fails(tmp_path: Path) -> None:
    pack = _pack(tmp_path, edit=lambda root: (root / "PatchBook.pdf").write_bytes(b"%PDF-1.4 junk"))
    assert _codes(_read(pack)) == {"PDF_UNREADABLE"}


def test_pages_with_no_text_fail(tmp_path: Path) -> None:
    """A book drawn as images would otherwise have nothing for these rules to find."""

    def blank(root: Path) -> None:
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=612, height=792)
        with (root / "PatchBook.pdf").open("wb") as handle:
            writer.write(handle)

    report = _read(_pack(tmp_path, edit=blank))
    assert [f["page"] for f in report["failures"] if f["code"] == "PAGE_TEXT_EMPTY"] == [0, 1, 2]


def test_a_book_with_no_patch_pages_fails(tmp_path: Path) -> None:
    def no_patch_pages(root: Path) -> None:
        book = root / "validation" / "book.json"
        pages = [{**page, "kind": "front_matter"} for page in json.loads(book.read_text())["pages"]]
        _edit_json(book, pages=pages)

    assert _codes(_read(_pack(tmp_path, edit=no_patch_pages))) == {"NO_PATCH_PAGES"}


def test_a_patch_page_with_no_page_data_fails(tmp_path: Path) -> None:
    pack = _pack(tmp_path, edit=lambda root: shutil.rmtree(root / "pages" / "json"))
    assert _read(pack)["failures"] == [{"code": "PAGE_DATA_MISSING", "page": 1}]


def test_a_book_that_did_not_pass_validation_fails(tmp_path: Path) -> None:
    pack = _pack(
        tmp_path, edit=lambda root: _edit_json(root / "validation" / "book.json", status="fail")
    )
    assert _codes(_read(pack)) == {"BOOK_VALIDATION_NOT_PASSED"}


def test_the_count_of_distinct_operation_texts_sees_identical_pages(tmp_path, monkeypatch) -> None:
    """Identical Operation text isn't a failure here, but the receipt shows it."""
    monkeypatch.setattr(engine, "operation_lines", lambda *args: ["Power up."])
    two = [
        replace(_library().items[0], position=0),
        replace(_library(_patch(id=6, name="Slate")).items[0], position=1),
    ]
    library = replace(_library(), items=tuple(two))
    report = _read(_pack(tmp_path, library))
    assert report["counts"]["patch_pages"] == 2
    assert report["counts"]["distinct_operation_texts"] == 1


# --- the walkthrough: generate, export with test credits, download, read ----------

FLAGS = runtime_flags_payload(
    SimpleNamespace(
        environment="staging",
        enable_patchbook_design_engine=True,
        enable_canon_export_fulfillment=True,
        enable_inline_export_fulfillment=True,
        enable_patchbook_publication_profile=False,
        stripe_test_mode=True,
        allow_production_payments=False,
    )
)
GOOD_RUN = {
    "status": "succeeded",
    "failure_reason": None,
    "export_bridge_ready": True,
    "source_run_id": RUN,
    "rig_revision_id": "rig-rev-" + "a" * 32,
    "artifact_manifest_hash": "b" * 64,
}
GENERATED = {"generated_count": 1, "run_id": 19, "patches": [{"generation_version": "1.2.0"}]}


class _Api:
    """The staging API's answers. ``answers`` replaces one path's answer."""

    def __init__(self, pack: bytes, **answers: httpx.Response) -> None:
        self.pack, self.answers, self.calls, self.bodies = pack, answers, [], {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        if request.content:
            self.bodies[path] = json.loads(request.content)
        replaced = self.answers.get(path)
        if replaced is not None:
            return replaced
        if path == "/api/community/auth/login":
            body = json.loads(request.content)
            return httpx.Response(
                200, json={"access_token": f"token-{body['username']}", "user": {"id": 5}}
            )
        export = {"id": "exp-1", "status": "succeeded", "pack_manifest_hash": "m" * 64}
        routes: dict[str, tuple[int, Any]] = {
            "/health/ready": (200, {"status": "healthy", "database": "ok"}),
            "/api/admin/ops/runtime-flags": (200, FLAGS),
            "/api/racks/": (200, {"racks": [{"id": 7}]}),
            "/api/patches/generate/7": (200, GENERATED),
            "/api/runs/19": (200, GOOD_RUN),
            "/api/canon/exports/preview": (200, {"style_recipe_hash": "h" * 64}),
            "/api/admin/users/5/credits/grant": (201, {}),
            "/api/canon/exports": (201, export),
            "/api/canon/exports/exp-1/download-token": (200, {"token": "download-token-for-tests"}),
        }
        if path == "/api/canon/exports/exp-1/artifacts/zip":
            return httpx.Response(200, content=self.pack)
        status, body = routes[path]
        return httpx.Response(status, json=body)

    def client(self) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(self), base_url="https://api-staging.example"
        )


def _walk(api: _Api) -> dict[str, Any]:
    with api.client() as http:
        return check.run_check(http, USER, ADMIN, "1.2.0")


def test_the_walkthrough_exports_the_generated_run_and_reads_its_pdf(tmp_path: Path) -> None:
    api = _Api(_pack(tmp_path))
    result = _walk(api)
    assert result["outcome"] == "PASS", result
    assert result["pages"]["status"] == "pass"
    assert [step["step"] for step in result["steps"]][-2:] == ["pdf_pages", "server_flags"]
    # The credits are test credits for this user, and the export is of the run just generated.
    assert "/api/admin/users/5/credits/grant" in api.calls
    body = api.bodies["/api/canon/exports"]
    assert body["source_run_id"] == RUN
    assert body["source_rig_revision_id"] == GOOD_RUN["rig_revision_id"]
    assert body["artifact_manifest_hash"] == GOOD_RUN["artifact_manifest_hash"]


def test_a_bad_page_fails_the_walkthrough(tmp_path: Path, monkeypatch) -> None:
    real = engine.operation_lines
    monkeypatch.setattr(engine, "operation_lines", lambda *args: [*real(*args), "[prep] Go."])
    result = _walk(_Api(_pack(tmp_path)))
    assert result["outcome"] == "FAIL"
    assert result["pages"]["failures"] == [{"code": "PAGE_PRINTS_PHASE_TAG", "page": 1}]
    assert {"step": "pdf_pages", "status": None, "code": None, "ok": False} in result["steps"]


@pytest.mark.parametrize(
    "flags",
    [
        {**FLAGS, "stripe_test_mode": False},
        {**FLAGS, "allow_production_payments": True},
        {**FLAGS, "environment": "production"},
    ],
)
def test_a_server_not_in_test_mode_is_refused_before_anything_is_generated(flags) -> None:
    api = _Api(b"", **{"/api/admin/ops/runtime-flags": httpx.Response(200, json=flags)})
    result = _walk(api)
    assert result["outcome"] == "FAIL" and result["steps"][-1]["step"] == "server_flags"
    assert not any(
        "generate" in call or "credits" in call or "exports" in call for call in api.calls
    )


def test_flags_that_change_during_the_check_fail_it(tmp_path: Path) -> None:
    api = _Api(_pack(tmp_path))
    real = api.__call__
    seen = {"count": 0}

    def changing(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/admin/ops/runtime-flags":
            seen["count"] += 1
            if seen["count"] > 1:
                changed = {**FLAGS, "enable_patchbook_publication_profile": True}
                return httpx.Response(200, json=changed)
        return real(request)

    with httpx.Client(
        transport=httpx.MockTransport(changing), base_url="https://api-staging.example"
    ) as http:
        result = check.run_check(http, USER, ADMIN, "1.2.0")
    assert result["outcome"] == "FAIL" and result["steps"][-1]["code"] == "SERVER_FLAGS_CHANGED"


def test_a_failed_generate_stops_before_any_credit_is_granted() -> None:
    answer = httpx.Response(
        200,
        json={
            "generated_count": 0,
            "run_id": None,
            "patches": [],
            "generation_status": "NOT_COMPUTABLE",
            "inventory_gate_messages": ["Mutable Instruments Plaits is not confirmed"],
        },
    )
    api = _Api(b"", **{"/api/patches/generate/7": answer})
    result = _walk(api)
    assert result["outcome"] == "FAIL"
    assert not any("credits" in call for call in api.calls)
    # generate_check keeps that message in its own receipt. This receipt holds no names.
    assert "Plaits" not in json.dumps(result)


def test_a_run_with_no_export_bridge_stops_before_any_credit_is_granted() -> None:
    not_ready = httpx.Response(200, json={**GOOD_RUN, "export_bridge_ready": False})
    api = _Api(b"", **{"/api/runs/19": not_ready})
    result = _walk(api)
    assert result["outcome"] == "FAIL" and result["steps"][-1]["step"] == "export_bridge_ready"
    assert not any("credits" in call for call in api.calls)


def test_a_failed_download_fails_and_reads_nothing() -> None:
    gone = httpx.Response(503, json={"detail": "STORAGE_UNAVAILABLE"})
    result = _walk(_Api(b"", **{"/api/canon/exports/exp-1/artifacts/zip": gone}))
    assert result["outcome"] == "FAIL" and "pages" not in result
    assert result["steps"][-1] == {
        "step": "download_pack",
        "status": 503,
        "code": None,
        "ok": False,
    }


def test_a_sign_in_that_does_not_say_who_it_is_fails() -> None:
    api = _Api(b"")
    real = api.__call__
    logins = {"count": 0}

    def forgetful(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/community/auth/login":
            logins["count"] += 1
            # The admin's flag check, then generate_check, then the sign-in for the export.
            if logins["count"] == 3:
                return httpx.Response(200, json={"access_token": "t"})
        return real(request)

    with httpx.Client(
        transport=httpx.MockTransport(forgetful), base_url="https://api-staging.example"
    ) as http:
        result = check.run_check(http, USER, ADMIN, "1.2.0")
    assert result["outcome"] == "FAIL" and result["steps"][-1]["step"] == "login_for_export"


# --- what reaches the public log and artifact -----------------------------------------

PRIVATE = (
    "Basalt",
    "A voice",
    "Plaits",
    "Polaris",
    "Maths",
    "Audio Out",
    "Power down",
    USER.password,
    ADMIN.password,
    "token-",
    "download-token-for-tests",
)


@pytest.mark.parametrize("bad", [False, True])
def test_the_receipt_and_the_log_hold_no_page_text_or_secret(
    tmp_path, monkeypatch, capsys, bad
) -> None:
    if bad:
        real = engine.operation_lines
        monkeypatch.setattr(engine, "operation_lines", lambda *args: [*real(*args), "UNKNOWN"])
    api = _Api(_pack(tmp_path / "built"))
    real_client = httpx.Client
    monkeypatch.setattr(
        check.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(api), **kwargs),
    )
    monkeypatch.setattr(check, "expected_engine_version", lambda: "1.2.0")
    monkeypatch.setenv("STAGING_API_URL", "https://api-staging.patch-hive.com")
    monkeypatch.setenv("PATCHHIVE_DEMO_USER_PASSWORD", USER.password)
    monkeypatch.setenv("PATCHHIVE_DEMO_ADMIN_PASSWORD", ADMIN.password)
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(out)

    assert check.main(["--receipt-out", "receipt.json"]) == (1 if bad else 0)

    # The job's workspace gains the receipt and nothing else: no pack, no PDF.
    assert [path.name for path in out.iterdir()] == ["receipt.json"]
    receipt = (out / "receipt.json").read_text(encoding="utf-8")
    captured = capsys.readouterr()
    for text in (receipt, captured.out, captured.err):
        for private in PRIVATE:
            assert private not in text
    loaded = json.loads(receipt)
    assert loaded["schema_version"] == check.SCHEMA
    assert loaded["outcome"] == ("FAIL" if bad else "PASS")
    assert set(loaded["pages"]["hashes"]) == {"pack_zip_sha256", "pdf_sha256"}


def test_main_refuses_a_non_staging_api(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STAGING_API_URL", "https://api.patch-hive.com")
    monkeypatch.setenv("PATCHHIVE_DEMO_USER_PASSWORD", USER.password)
    monkeypatch.setenv("PATCHHIVE_DEMO_ADMIN_PASSWORD", ADMIN.password)
    assert check.main(["--receipt-out", str(tmp_path / "r.json")]) == 2
    assert not (tmp_path / "r.json").exists()


@pytest.mark.parametrize(
    "missing", ["PATCHHIVE_DEMO_USER_PASSWORD", "PATCHHIVE_DEMO_ADMIN_PASSWORD"]
)
def test_main_refuses_without_both_passwords(monkeypatch, tmp_path: Path, missing: str) -> None:
    monkeypatch.setenv("STAGING_API_URL", "https://api-staging.patch-hive.com")
    monkeypatch.setenv("PATCHHIVE_DEMO_USER_PASSWORD", USER.password)
    monkeypatch.setenv("PATCHHIVE_DEMO_ADMIN_PASSWORD", ADMIN.password)
    monkeypatch.delenv(missing)
    assert check.main(["--receipt-out", str(tmp_path / "r.json")]) == 2


def _workflow_steps() -> list[dict[str, Any]]:
    path = ROOT / ".github" / "workflows" / "staging-walkthrough.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["staging"]["steps"]


def test_the_workflow_runs_the_check_and_keeps_only_receipts() -> None:
    steps = _workflow_steps()
    run = next(s for s in steps if "generated_export_check.py" in str(s.get("run")))
    assert "--receipt-out generated-export-receipt.json" in run["run"]
    assert "both" in run["if"] and "generated-export" in run["if"]
    assert "continue-on-error" not in run

    uploads = [s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact")]
    assert len(uploads) == 1
    paths = uploads[0]["with"]["path"].split()
    assert "generated-export-receipt.json" in paths
    assert all(path.endswith("-receipt.json") for path in paths)

    installs = [s["run"] for s in steps if "pip install" in str(s.get("run"))]
    assert installs == ["python -m pip install -e '.[staging-check]'"]


def test_the_pdf_reader_stays_out_of_what_the_api_installs() -> None:
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    project = project["project"]
    assert not any("pypdf" in dep for dep in project["dependencies"])
    assert "pypdf" not in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    pins = {
        name: [d for d in project["optional-dependencies"][name] if "pypdf" in d]
        for name in ("dev", "staging-check")
    }
    assert pins["dev"] == pins["staging-check"] and len(pins["dev"]) == 1


# --- the same check against the real routes, on the rig the staging job seeds ----------


def test_a_run_generated_on_the_seeded_rig_through_the_real_routes_passes(
    db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    """Generate, debit, compose, zip and download are the code staging runs, on SQLite."""
    from core import get_db
    from core.config import settings
    from main import app

    for name, value in {
        "environment": "staging",
        "enable_patchbook_design_engine": True,
        "enable_canon_export_fulfillment": True,
        "enable_inline_export_fulfillment": True,
        "stripe_test_mode": True,
        "allow_production_payments": False,
        "export_store_root": str(tmp_path),
        "export_dir": str(tmp_path),
        "download_token_secret": "x" * 40,
    }.items():
        monkeypatch.setattr(settings, name, value)
    check.demo_accounts("unused", "unused")  # leaves the seeder in sys.modules
    seeder = sys.modules["seed_golden_demo"]
    seeded = seeder.seed_golden_demo(db_session, environment="test")
    user = SeedAccount(seeded.username, seeded.password, seeder.DEMO_USER_ROLE)
    admin = SeedAccount(seeded.admin_username, seeded.admin_password, seeder.DEMO_ADMIN_ROLE)

    def override_get_db():
        yield db_session

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)
    http = TestClient(app)
    version = check.expected_engine_version()
    # The job's generate step has already run on this rack, so this is its second run.
    assert check.generate_run(http, user.username, user.password, version)["outcome"] == "PASS"
    result = check.run_check(http, user, admin, version)

    assert result["outcome"] == "PASS", result
    pages = result["pages"]
    assert pages["load_path"] == "generated_patches"
    generate = next(step for step in result["steps"] if step["step"] == "generate")
    assert pages["counts"]["patches"] == generate["generated_count"] >= 1
    assert pages["counts"]["pdf_pages"] == pages["counts"]["patch_pages"] + 2
    assert pages["counts"]["distinct_operation_texts"] > 1
