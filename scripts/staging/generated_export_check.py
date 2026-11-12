#!/usr/bin/env python3
"""Export a run generated through the API on staging, then read the pages of its PDF.

The Design Engine walkthrough exports the seeded demo's run, which has no sealed rows and loads as
``compile_on_export``. ``generate_check.py`` generates a run but never exports it. This takes the
path a customer takes: generate, export with test credits, download the zip, and open
``PatchBook.pdf`` to read what each page prints. ``validate_book`` reads the layout data, so it
can't see a page that prints the wrong thing.

Environment: STAGING_API_URL, PATCHHIVE_DEMO_USER_PASSWORD, PATCHHIVE_DEMO_ADMIN_PASSWORD (the
passwords the seeder set). The repo is public, so its workflow logs and artifacts are too. The pack
stays in memory and is never written to disk, and the receipt and this script's output hold
statuses, counts and hashes only: no password, token, page text or module name.

Usage (repo root):
  python scripts/staging/generated_export_check.py --receipt-out generated-export-receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import unicodedata
import zipfile
from collections import Counter
from itertools import takewhile
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "staging"))

from core.ops.design_walkthrough import execute_walkthrough, verify_server_flags  # noqa: E402
from core.ops.f5_cutover import CutoverError, SeedAccount  # noqa: E402
from evidence_resolution_check import _code, _demo_username, _json  # noqa: E402
from generate_check import expected_engine_version  # noqa: E402
from generate_check import run_check as generate_run  # noqa: E402

SCHEMA = "patchhive.staging-generated-export-check.v1"
EXPECTED_LOAD_PATH = "generated_patches"
LOAD_PATHS = {EXPECTED_LOAD_PATH, "compile_on_export"}
PATCH_PAGE_KINDS = {"execution", "appendix_execution"}

# What a seal writes when a fact is missing (engine.PLACEHOLDERS), and the plan's phases
# (canon/compiler.py). Cable lines end in a signal tag such as [audio], which is fine to print.
PLACEHOLDERS = ("UNKNOWN", "NOT_COMPUTABLE")
PHASE_TAGS = ("[prep]", "[threshold]", "[peak]", "[release]", "[seal]")
PADDING = "verifypriorconnection"
# A port id is module:jack:direction, as in 10:Audio Out:output. Whitespace is gone by the time
# this runs. "|" stops a match running across the page footer.
RAW_PORT_ID = re.compile(r"\d+:[^:|]{1,80}:(?:input|output)")
FIRST_NUMBERED_LINE = re.compile(r"1\.\s")
# Operation stops at the Warnings heading or at the footer, which is different on every page.
AFTER_OPERATION = re.compile(r"Warnings$| \| execution \| ")


def squeeze(text: str) -> str:
    """Text without whitespace, because a line can wrap anywhere in a name or an id."""
    return "".join(unicodedata.normalize("NFKC", text).split())


def page_text_failures(text: str) -> list[str]:
    """What no page of a book may print, cover and colophon included."""
    squeezed = squeeze(text)
    lowered = squeezed.lower()
    codes = []
    if not squeezed:
        codes.append("PAGE_TEXT_EMPTY")
    if any(placeholder in squeezed for placeholder in PLACEHOLDERS):
        codes.append("PAGE_PRINTS_PLACEHOLDER")
    if any(tag in lowered for tag in PHASE_TAGS):
        codes.append("PAGE_PRINTS_PHASE_TAG")
    if PADDING in lowered:
        codes.append("PAGE_PRINTS_PADDING")
    if RAW_PORT_ID.search(squeezed):
        codes.append("PAGE_PRINTS_RAW_PORT_ID")
    return codes


def split_sections(text: str) -> tuple[list[str] | None, list[str] | None]:
    """The lines under the Construction and Operation headings, or None for a missing one.

    The check exports the default Signal Manual family. Field Notes calls this Operation section
    Checklist, so a change of default family fails here until someone looks at it.
    """
    lines = [line.strip() for line in text.splitlines()]
    construction = lines.index("Construction") if "Construction" in lines else None
    operation = lines.index("Operation") if "Operation" in lines else None
    steps = None
    if operation is not None:
        steps = list(
            takewhile(lambda line: not AFTER_OPERATION.search(line), lines[operation + 1 :])
        )
    return (None if construction is None else lines[construction + 1 : operation], steps)


def has_a_first_step(section: list[str] | None) -> bool:
    return bool(section) and any(FIRST_NUMBERED_LINE.match(line) for line in section)


def is_named(module_id: str, label: str) -> bool:
    """Brand and name: at least two words, and not the "Module 10" a sealed graph falls back to."""
    return len(label.split()) >= 2 and label != f"Module {module_id}"


def unnamed_modules(page: dict[str, Any], construction: list[str], text: str) -> int:
    """How many of the page's modules it doesn't print by brand and name.

    Each cable has to name its modules, so a module's name has to appear in the Construction list
    at least once per cable end. A book that switches to an id from some cable on still prints the
    name in its diagram and on its earlier cables.
    """
    modules = {str(key): str(value) for key, value in (page.get("modules") or {}).items()}
    edges = (page.get("graph") or {}).get("edges") or []
    cable_ends = Counter(
        str(edge[end]).split(":", 1)[0]
        for edge in edges
        for end in ("source_port_id", "target_port_id")
    )
    listed = squeeze(" ".join(construction))
    whole_page = squeeze(text)
    missing = 0
    for module_id in sorted(set(modules) | set(cable_ends)):
        label = modules.get(module_id, "")
        name = squeeze(label)
        if not is_named(module_id, label) or name not in whole_page:
            missing += 1
        elif listed.count(name) < cable_ends[module_id]:
            missing += 1
    return missing


def check_pack(pack: bytes, *, source_run_id: str) -> dict[str, Any]:
    """Read a downloaded pack. The result holds codes, page indexes, counts and hashes only."""
    failures: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    hashes = {"pack_zip_sha256": hashlib.sha256(pack).hexdigest()}
    result = {"failures": failures, "counts": counts, "hashes": hashes, "load_path": None}

    def done() -> dict[str, Any]:
        return {"status": "fail" if failures else "pass", **result}

    def fail(code: str, **where: Any) -> None:
        failures.append({"code": code, **where})

    try:
        archive = zipfile.ZipFile(io.BytesIO(pack))
    except zipfile.BadZipFile:
        fail("PACK_UNREADABLE")
        return done()

    def read_json(name: str) -> dict[str, Any] | None:
        try:
            loaded = json.loads(archive.read(name))
        except (KeyError, ValueError):
            fail("PACK_FILE_UNREADABLE", file=name)
            return None
        if not isinstance(loaded, dict):
            fail("PACK_FILE_UNREADABLE", file=name)
            return None
        return loaded

    library = read_json("source/library_index.json")
    book = read_json("validation/book.json")
    if "PatchBook.pdf" not in archive.namelist():
        fail("PACK_FILE_UNREADABLE", file="PatchBook.pdf")
    if library is None or book is None or failures:
        return done()

    load_path = library.get("load_path")
    result["load_path"] = load_path if load_path in LOAD_PATHS else "other"
    if load_path != EXPECTED_LOAD_PATH:
        fail("EXPORT_NOT_GENERATED_PATCHES")
    if library.get("source_run_id") != source_run_id:
        fail("EXPORT_NOT_THE_GENERATED_RUN")
    if book.get("status") != "pass":
        fail("BOOK_VALIDATION_NOT_PASSED")

    pdf = archive.read("PatchBook.pdf")
    hashes["pdf_sha256"] = hashlib.sha256(pdf).hexdigest()
    try:
        texts = [page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages]
    except Exception:  # pypdf raises many types on a damaged file, and none may stop the receipt.
        fail("PDF_UNREADABLE")
        return done()

    book_pages = book.get("pages") or []
    counts.update(
        pdf_pages=len(texts),
        book_pdf_pages=int(book.get("pdf_page_count") or 0),
        book_manifest_pages=int(book.get("manifest_page_count") or 0),
        book_page_entries=len(book_pages),
        patches=len(library.get("patches") or []),
    )
    if {counts["book_pdf_pages"], counts["book_manifest_pages"], len(book_pages)} != {len(texts)}:
        fail("PDF_PAGE_COUNT_MISMATCH")

    for index, text in enumerate(texts):
        for code in page_text_failures(text):
            fail(code, page=index)

    page_data = {}
    for name in archive.namelist():
        if name.startswith("pages/json/") and name.endswith(".json"):
            data = read_json(name)
            if data is not None:
                page_data[data.get("page_index")] = data

    patch_pages = [entry["index"] for entry in book_pages if entry.get("kind") in PATCH_PAGE_KINDS]
    if not patch_pages:
        fail("NO_PATCH_PAGES")
    operations = set()
    modules_checked = 0
    cables_checked = 0
    for index in patch_pages:
        if index >= len(texts):
            continue  # already reported as a page count mismatch
        data = page_data.get(index)
        if data is None:
            fail("PAGE_DATA_MISSING", page=index)
            continue
        construction, operation = split_sections(texts[index])
        if not has_a_first_step(construction):
            fail("PAGE_MISSING_CONSTRUCTION", page=index)
        if not has_a_first_step(operation):
            fail("PAGE_MISSING_OPERATION", page=index)
        operations.add(hashlib.sha256(squeeze(" ".join(operation or [])).encode()).hexdigest())
        modules_checked += len(data.get("modules") or {})
        cables_checked += len((data.get("graph") or {}).get("edges") or [])
        unnamed = unnamed_modules(data, construction or [], texts[index])
        if unnamed:
            fail("MODULE_NOT_NAMED", page=index, count=unnamed)
    counts.update(
        patch_pages=len(patch_pages),
        modules_checked=modules_checked,
        cables_checked=cables_checked,
        distinct_operation_texts=len(operations),
    )
    # Steps are written from each patch's own cables (#329), so one text on every page means
    # they stopped being.
    if len(patch_pages) > 1 and len(operations) == 1:
        fail("OPERATION_TEXT_REPEATED")
    return done()


def run_check(
    http: httpx.Client, user: SeedAccount, admin: SeedAccount, engine_version: str
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    def record(step: str, ok: bool, *, status: int | None = None, code: str | None = None) -> bool:
        steps.append({"step": step, "status": status, "code": code, "ok": ok})
        return ok

    def stop() -> dict[str, Any]:
        return {"outcome": "FAIL", "steps": steps}

    def server_flags() -> Any:
        """Test payments and staging only, or nothing gets generated or debited (spec 008 R2)."""
        try:
            flags = verify_server_flags(http, admin=admin, expected_environment="staging")
        except CutoverError as exc:
            record("server_flags", False, code=exc.code)
            return None
        record("server_flags", True)
        return flags

    flags = server_flags()
    if flags is None:
        return stop()

    generated = generate_run(http, user.username, user.password, engine_version)
    # generate_check's steps can carry inventory messages, which name modules. Keep only these.
    kept = ("step", "status", "code", "ok", "generated_count")
    steps.extend({key: step[key] for key in kept if key in step} for step in generated["steps"])
    if generated["outcome"] != "PASS":
        return stop()

    resp = http.post(
        "/api/community/auth/login", json={"username": user.username, "password": user.password}
    )
    body = _json(resp) if resp.status_code == 200 else None
    body = body if isinstance(body, dict) else {}
    token, user_id = body.get("access_token"), (body.get("user") or {}).get("id")
    if not record(
        "login_for_export", bool(token and user_id), status=resp.status_code, code=_code(body)
    ):
        return stop()

    resp = http.get(
        f"/api/runs/{generated['run_id']}", headers={"Authorization": f"Bearer {token}"}
    )
    run = _json(resp) if resp.status_code == 200 else None
    run = run if isinstance(run, dict) else {}
    if not record(
        "export_bridge_ready",
        run.get("export_bridge_ready") is True,
        status=resp.status_code,
        code=_code(run),
    ):
        return stop()
    sources = {
        "source_run_id": run["source_run_id"],
        "source_rig_revision_id": run["rig_revision_id"],
        "artifact_manifest_hash": run["artifact_manifest_hash"],
    }

    packs: list[bytes] = []
    _, walkthrough = execute_walkthrough(
        http, user=user, admin=admin, user_id=int(user_id), sources=sources, on_pack=packs.append
    )
    for walked in walkthrough.steps:
        record(walked.name, walked.passed, status=walked.http_status)
    if not walkthrough.passed or not packs:
        return stop()

    pages = check_pack(packs[0], source_run_id=sources["source_run_id"])
    record("pdf_pages", pages["status"] == "pass")

    after = server_flags()
    if after is not None and after != flags:
        record("server_flags_unchanged", False, code="SERVER_FLAGS_CHANGED")
    outcome = "PASS" if all(step["ok"] for step in steps) else "FAIL"
    return {
        "outcome": outcome,
        "steps": steps,
        "pages": pages,
        "pack_manifest_hash": walkthrough.pack_manifest_hash,
        "composition_hash": walkthrough.composition_hash,
    }


def demo_accounts(user_password: str, admin_password: str) -> tuple[SeedAccount, SeedAccount]:
    username = _demo_username()  # leaves the seeder in sys.modules for its other constants
    seeder = sys.modules["seed_golden_demo"]
    return (
        SeedAccount(username, user_password, seeder.DEMO_USER_ROLE),
        SeedAccount(seeder.DEMO_ADMIN_USERNAME, admin_password, seeder.DEMO_ADMIN_ROLE),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args(argv)
    api = os.environ.get("STAGING_API_URL", "").rstrip("/")
    user_password = os.environ.get("PATCHHIVE_DEMO_USER_PASSWORD", "")
    admin_password = os.environ.get("PATCHHIVE_DEMO_ADMIN_PASSWORD", "")
    if not api.startswith("https://api-staging.") or not user_password or not admin_password:
        print(
            "refused: set STAGING_API_URL to the staging API, PATCHHIVE_DEMO_USER_PASSWORD and "
            "PATCHHIVE_DEMO_ADMIN_PASSWORD",
            file=sys.stderr,
        )
        return 2
    user, admin = demo_accounts(user_password, admin_password)
    with httpx.Client(base_url=api, timeout=120.0) as http:
        result = run_check(http, user, admin, expected_engine_version())
    receipt = {
        "schema_version": SCHEMA,
        "api": api,
        "source_commit_sha": os.environ.get("WALKTHROUGH_SOURCE_SHA")
        or os.environ.get("GITHUB_SHA"),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **result,
    }
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    receipt["receipt_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    Path(args.receipt_out).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for step in result["steps"]:
        print(f"  {step['step']}: ok={step['ok']} status={step['status']} code={step['code']}")
    pages = result.get("pages") or {}
    print(f"  counts: {json.dumps(pages.get('counts') or {}, sort_keys=True)}")
    for failure in pages.get("failures") or []:
        print(f"  page failure: {json.dumps(failure, sort_keys=True)}")
    print(f"GENERATED EXPORT {result['outcome']} receipt_sha256={receipt['receipt_sha256']}")
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
