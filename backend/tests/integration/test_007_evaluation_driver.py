"""Spec 007 operator driver (scripts/staging/run_007_evaluation.py), offline.

Runs every subcommand on the synthetic chain from tests/eval007_helpers.py with the
fixture provider (``run --dry-run``), a throwaway in-memory Ed25519 key written to a
temporary PEM file, and a temporary allowlist, ending with ``verify`` passing. Then
the refusals: missing approval flag, unknown approver, tampered receipt, wrong key.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intelligence.contracts import ChoiceOption, stable_sha256
from tests.eval007_helpers import (
    HARNESS_SHA,
    SOURCE_SHA,
    admitted_manifest,
    assisted_cases,
    install_allowlist,
    throwaway_approver,
)

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "staging" / "run_007_evaluation.py"


@pytest.fixture(scope="module")
def driver():
    spec = importlib.util.spec_from_file_location("run_007_evaluation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidates(case: dict) -> list[dict]:
    expected = case["expected_choice"]
    ids = ["none_of_above", "maker:other"] if expected == "none_of_above" else [expected, "none_of_above"]
    return [{"choice_id": item} for item in ids]


def _write_pem(path: Path, key: Ed25519PrivateKey) -> Path:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    path.chmod(0o600)
    return path


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Synthetic manifest, run inputs, image files, fixture packets, key and allowlist."""
    manifest = admitted_manifest()
    # The candidate_set_hash a real operator records is the hash of the exact options
    # the provider is asked; the synthetic placeholders are replaced with that hash.
    for case in manifest["cases"]:
        options = tuple(ChoiceOption.model_validate(item) for item in _candidates(case))
        case["candidate_set_hash"] = "sha256:" + stable_sha256(options)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    images = tmp_path / "images"
    images.mkdir()
    inputs = {"schema_version": "patchhive.eval-run-inputs.v1", "cases": {}}
    for case in manifest["cases"]:
        entry = {"candidates": _candidates(case), "images": []}
        if int(case["case_id"].split("-")[1]) % 5 != 0:  # helpers' text-modality cases carry no image
            # eval007_helpers.image_hash(case_id) is the SHA-256 of the case id bytes.
            (images / f"{case['case_id']}.png").write_bytes(case["case_id"].encode("ascii"))
            entry["images"] = [f"images/{case['case_id']}.png"]
        inputs["cases"][case["case_id"]] = entry
    (tmp_path / "run-inputs.json").write_text(json.dumps(inputs), encoding="utf-8")

    fixtures = {
        row.case_id: {"selected_choice": row.packet.selected_choice, "probabilities": row.packet.probabilities}
        for row in assisted_cases(manifest, provider="nvidia")
    }
    (tmp_path / "fixture-packets.json").write_text(json.dumps(fixtures), encoding="utf-8")

    private_key, entry = throwaway_approver("approver-test")
    install_allowlist(monkeypatch, tmp_path, entry)
    key_path = _write_pem(tmp_path / "approver.pem", private_key)
    return {"root": tmp_path, "dir": tmp_path / "chain", "key": key_path}


def _cli(driver, ws, *args: str) -> int:
    return driver.main(["--provider", "nvidia", "--dir", str(ws["dir"]), *args])


def _through_staging(driver, ws) -> None:
    root = ws["root"]
    assert _cli(driver, ws, "freeze", "--manifest", str(root / "manifest.json")) == 0
    assert _cli(
        driver, ws, "run", "--dry-run",
        "--inputs", str(root / "run-inputs.json"),
        "--fixture-packets", str(root / "fixture-packets.json"),
        "--harness-sha", HARNESS_SHA,
        "--manifest", str(root / "manifest.json"),
    ) == 0
    assert _cli(driver, ws, "propose", "--proposal-version", "thresholds-v1") == 0
    assert _cli(driver, ws, "approve", "--approved-by", "approver-test", "--yes-i-approve") == 0
    assert _cli(driver, ws, "enable-staging") == 0


def _full_chain(driver, ws) -> None:
    _through_staging(driver, ws)
    assert _cli(driver, ws, "pin", "--source-commit-sha", SOURCE_SHA) == 0
    assert _cli(driver, ws, "sign", "--key", str(ws["key"])) == 0


def test_every_subcommand_end_to_end_and_verify_passes(driver, workspace, capsys):
    _full_chain(driver, workspace)
    assert _cli(driver, workspace, "verify") == 0
    out = capsys.readouterr().out
    assert "chain replay: yes" in out
    assert out.rstrip().endswith("PASS")
    assert "DRY RUN" in out

    chain = workspace["dir"]
    for name in ("corpus", "run", "proposal", "approval", "staging", "receipt", "signature"):
        assert (chain / f"{name}.json").is_file()
    assert (chain / "DRY_RUN").is_file()
    receipt = json.loads((chain / "receipt.json").read_text())
    signature = json.loads((chain / "signature.json").read_text())
    assert receipt["providers"] == ["nvidia"]
    assert receipt["approved_by"] == "approver-test"
    assert receipt["source_commit_sha"] == SOURCE_SHA
    assert signature["receipt_sha256"] == receipt["receipt_sha256"]
    assert signature["key_id"] == "approver-test"
    # A dry run never prints container settings and never holds key material.
    assert "DECISION_ENABLEMENT_RECEIPT_PATH=" not in out
    assert "PRIVATE KEY" not in out
    assert "PRIVATE KEY" not in (chain / "signature.json").read_text()


def test_approve_without_explicit_flag_is_refused(driver, workspace, capsys):
    root = workspace["root"]
    assert _cli(driver, workspace, "freeze", "--manifest", str(root / "manifest.json")) == 0
    assert _cli(
        driver, workspace, "run", "--dry-run",
        "--inputs", str(root / "run-inputs.json"),
        "--fixture-packets", str(root / "fixture-packets.json"),
        "--harness-sha", HARNESS_SHA,
    ) == 0
    assert _cli(driver, workspace, "propose", "--proposal-version", "thresholds-v1") == 0
    assert _cli(driver, workspace, "approve", "--approved-by", "approver-test") == 1
    assert "EXPLICIT_SIGN_OFF_REQUIRED" in capsys.readouterr().err
    assert not (workspace["dir"] / "approval.json").exists()


def test_unknown_approver_is_refused(driver, workspace, capsys):
    root = workspace["root"]
    assert _cli(driver, workspace, "freeze", "--manifest", str(root / "manifest.json")) == 0
    assert _cli(
        driver, workspace, "run", "--dry-run",
        "--inputs", str(root / "run-inputs.json"),
        "--fixture-packets", str(root / "fixture-packets.json"),
        "--harness-sha", HARNESS_SHA,
    ) == 0
    assert _cli(driver, workspace, "propose", "--proposal-version", "thresholds-v1") == 0
    assert _cli(driver, workspace, "approve", "--approved-by", "someone-else", "--yes-i-approve") == 1
    assert "APPROVER_KEY_UNKNOWN" in capsys.readouterr().err
    assert not (workspace["dir"] / "approval.json").exists()


def test_tampered_receipt_fails_verify(driver, workspace, capsys):
    _full_chain(driver, workspace)
    path = workspace["dir"] / "receipt.json"
    receipt = json.loads(path.read_text())
    receipt["assisted_metrics"]["top1_accuracy"] = 0.5
    path.write_text(json.dumps(receipt, indent=2))
    assert _cli(driver, workspace, "verify") == 1
    err = capsys.readouterr().err
    assert "VERIFY_FAILED" in err
    assert "RECEIPT_SHA_MISMATCH" in err


def test_signing_with_a_key_that_is_not_the_approver_key_is_refused(driver, workspace, capsys):
    _through_staging(driver, workspace)
    assert _cli(driver, workspace, "pin", "--source-commit-sha", SOURCE_SHA) == 0
    wrong = _write_pem(workspace["root"] / "wrong.pem", Ed25519PrivateKey.generate())
    assert _cli(driver, workspace, "sign", "--key", str(wrong)) == 1
    assert "SIGNING_KEY_NOT_APPROVER_KEY" in capsys.readouterr().err
    assert not (workspace["dir"] / "signature.json").exists()


def test_signature_from_a_wrong_key_fails_verify(driver, workspace, capsys):
    from intelligence.receipt_signing import sign_receipt_sha256

    _through_staging(driver, workspace)
    assert _cli(driver, workspace, "pin", "--source-commit-sha", SOURCE_SHA) == 0
    receipt = json.loads((workspace["dir"] / "receipt.json").read_text())
    forged = sign_receipt_sha256(
        Ed25519PrivateKey.generate(), key_id="approver-test", receipt_sha256=receipt["receipt_sha256"]
    )
    (workspace["dir"] / "signature.json").write_text(forged.model_dump_json(indent=2))
    assert _cli(driver, workspace, "verify") == 1
    assert "SIGNATURE_INVALID" in capsys.readouterr().err


def test_dry_run_refuses_to_write_under_backend(driver, workspace, capsys):
    root = workspace["root"]
    code = driver.main([
        "--provider", "nvidia", "run", "--dry-run",
        "--inputs", str(root / "run-inputs.json"),
        "--fixture-packets", str(root / "fixture-packets.json"),
        "--harness-sha", HARNESS_SHA,
    ])
    assert code == 1
    assert "DRY_RUN_UNDER_BACKEND" in capsys.readouterr().err


def test_live_run_refuses_without_the_provider_flag(driver, workspace, capsys, monkeypatch):
    monkeypatch.delenv("ENABLE_NVIDIA_PROVIDER", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    root = workspace["root"]
    live = {"root": root, "dir": root / "live", "key": workspace["key"]}
    assert _cli(driver, live, "freeze", "--manifest", str(root / "manifest.json")) == 0
    assert _cli(
        driver, live, "run", "--inputs", str(root / "run-inputs.json"), "--harness-sha", HARNESS_SHA
    ) == 1
    assert "PROVIDER_FLAG_OFF" in capsys.readouterr().err
    assert not (live["dir"] / "run.json").exists()


def test_candidate_set_that_does_not_match_the_frozen_hash_is_refused(driver, workspace, capsys):
    root = workspace["root"]
    assert _cli(driver, workspace, "freeze", "--manifest", str(root / "manifest.json")) == 0
    inputs = json.loads((root / "run-inputs.json").read_text())
    first = sorted(inputs["cases"])[0]
    inputs["cases"][first]["candidates"].append({"choice_id": "maker:extra"})
    (root / "run-inputs.json").write_text(json.dumps(inputs))
    assert _cli(
        driver, workspace, "run", "--dry-run",
        "--inputs", str(root / "run-inputs.json"),
        "--fixture-packets", str(root / "fixture-packets.json"),
        "--harness-sha", HARNESS_SHA,
    ) == 1
    assert "CANDIDATE_SET_HASH_MISMATCH" in capsys.readouterr().err


def test_artifacts_are_never_overwritten(driver, workspace, capsys):
    root = workspace["root"]
    assert _cli(driver, workspace, "freeze", "--manifest", str(root / "manifest.json")) == 0
    assert _cli(driver, workspace, "freeze", "--manifest", str(root / "manifest.json")) == 1
    assert "ARTIFACT_EXISTS" in capsys.readouterr().err


def test_live_run_calls_the_provider_with_bound_images(driver, workspace, capsys, monkeypatch):
    """The live path with a mocked NVIDIA transport: no network, real adapter and loader."""
    import hashlib

    import httpx

    import intelligence.nvidia_provider as nvidia_provider

    root = workspace["root"]
    manifest = json.loads((root / "manifest.json").read_text())
    inputs = json.loads((root / "run-inputs.json").read_text())
    for case in manifest["cases"]:
        entry = inputs["cases"][case["case_id"]]
        if entry["images"]:
            data = b"\x89PNG\r\n\x1a\n" + case["case_id"].encode("ascii")
            (root / entry["images"][0]).write_bytes(data)
            case["image_asset_hashes"] = ["sha256:" + hashlib.sha256(data).hexdigest()]
    (root / "manifest.json").write_text(json.dumps(manifest))

    seen: list[dict] = []

    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        ids = body["response_format"]["json_schema"]["schema"]["properties"]["choice"]["enum"]
        others = [item for item in ids if item != ids[0]]
        probabilities = {ids[0]: 0.95, **{item: 0.05 / len(others) for item in others}}
        content = json.dumps({"type": "choice", "choice": ids[0], "probabilities": probabilities})
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]}
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        nvidia_provider.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(answer), **kwargs),
    )
    monkeypatch.setenv("ENABLE_NVIDIA_PROVIDER", "true")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key-not-real")

    assert _cli(driver, workspace, "freeze", "--manifest", str(root / "manifest.json")) == 0
    assert _cli(
        driver, workspace, "run", "--inputs", str(root / "run-inputs.json"), "--harness-sha", HARNESS_SHA
    ) == 0
    captured = capsys.readouterr()
    assert "test-key-not-real" not in captured.out + captured.err
    assert len(seen) == len(manifest["cases"])
    sent_images = [
        body
        for body in seen
        if any(part.get("type") == "image_url" for part in body["messages"][1]["content"])
    ]
    assert len(sent_images) == sum(1 for entry in inputs["cases"].values() if entry["images"])
    run = json.loads((workspace["dir"] / "run.json").read_text())
    assert run["assisted_provider_id"] == "nvidia"
    assert run["assisted"]["top1_accuracy"] == 1.0
    assert not (workspace["dir"] / "DRY_RUN").exists()
