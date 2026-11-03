"""Spec 008 T050b/T072 driver (scripts/staging/pin_readiness_008.py), on synthetic artifacts."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization

from tests.f5008_helpers import (
    APPROVER_ID,
    APPROVER_KEY,
    chain,
    docs,
    enablement_receipt,
    enablement_signature,
)
from tests.f5008_helpers import f5008_approver_allowlist  # noqa: F401  (autouse)

REPO = Path(__file__).resolve().parents[3]


def _driver():
    spec = importlib.util.spec_from_file_location(
        "pin_readiness_008", REPO / "scripts" / "staging" / "pin_readiness_008.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_docs(root: Path, text_by_path: dict[str, str]) -> Path:
    for rel, text in text_by_path.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def art(tmp_path_factory):
    d = tmp_path_factory.mktemp("pin")
    c = chain()
    bundle = {
        "alias_evidence": c["alias"].model_dump(mode="json"),
        "fe_cutover": c["fe"].model_dump(mode="json"),
        "walkthrough_start": c["start"].model_dump(mode="json"),
        "receipt": c["receipt"].model_dump(mode="json"),
    }
    (d / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    enablement = enablement_receipt()
    (d / "receipt.json").write_text(
        json.dumps(enablement.model_dump(mode="json")), encoding="utf-8"
    )
    (d / "signature.json").write_text(
        json.dumps(enablement_signature(enablement).model_dump(mode="json")),
        encoding="utf-8",
    )
    pem = APPROVER_KEY.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    (d / "key.pem").write_bytes(pem)
    (d / "key.pem").chmod(0o600)
    _write_docs(d / "repo", docs())
    _write_docs(d / "stale", docs(sha="0" * 40))
    return d


def _enablement_args(d: Path) -> list[str]:
    return [
        "--enablement-receipt",
        str(d / "receipt.json"),
        "--enablement-signature",
        str(d / "signature.json"),
    ]


def test_check_names_the_missing_007_receipt(art, capsys) -> None:
    code = _driver().main(
        ["--root", str(art / "repo"), "check", "--bundle", str(art / "bundle.json")]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "state: RECEIPT_CAPTURED" in out
    assert "no signed spec 007 receipt yet" in out


def test_check_names_docs_that_do_not_cite_the_sha(art, capsys) -> None:
    code = _driver().main(
        [
            "--root",
            str(art / "stale"),
            "check",
            "--bundle",
            str(art / "bundle.json"),
            *_enablement_args(art),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "does not cite the walkthrough source SHA" in out


def test_check_passes_when_everything_is_in_place(art, capsys) -> None:
    code = _driver().main(
        [
            "--root",
            str(art / "repo"),
            "check",
            "--bundle",
            str(art / "bundle.json"),
            *_enablement_args(art),
        ]
    )
    assert code == 0
    assert "ready to pin" in capsys.readouterr().out


def test_pin_then_replay_reaches_beta_eligible(art, capsys) -> None:
    driver = _driver()
    pin_path = art / "readiness-pin.json"
    code = driver.main(
        [
            "--root",
            str(art / "repo"),
            "pin",
            "--bundle",
            str(art / "bundle.json"),
            *_enablement_args(art),
            "--key",
            str(art / "key.pem"),
            "--pinned-by",
            APPROVER_ID,
            "--out",
            str(pin_path),
        ]
    )
    assert code == 0, capsys.readouterr().out
    assert json.loads(pin_path.read_text(encoding="utf-8"))["pinned_by"] == APPROVER_ID

    code = driver.main(
        ["replay", "--bundle", str(art / "bundle.json"), "--pin", str(pin_path)]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "state: BETA_ELIGIBLE" in out
    assert "beta_eligible: True" in out


def test_an_open_p0_refuses_the_pin(art, tmp_path, capsys) -> None:
    p0 = tmp_path / "p0.txt"
    p0.write_text("P0-1 export debit charged twice\n", encoding="utf-8")
    code = _driver().main(
        [
            "--root",
            str(art / "repo"),
            "pin",
            "--bundle",
            str(art / "bundle.json"),
            *_enablement_args(art),
            "--unresolved-p0",
            str(p0),
            "--key",
            str(art / "key.pem"),
            "--pinned-by",
            APPROVER_ID,
            "--out",
            str(tmp_path / "pin.json"),
        ]
    )
    assert code == 2
    assert "UNRESOLVED_P0" in capsys.readouterr().out
    assert not (tmp_path / "pin.json").exists()


def test_a_tampered_bundle_does_not_replay(art, tmp_path, capsys) -> None:
    bundle = json.loads((art / "bundle.json").read_text(encoding="utf-8"))
    bundle["receipt"]["source_commit_sha"] = "1" * 40
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps(bundle), encoding="utf-8")
    code = _driver().main(
        [
            "--root",
            str(art / "repo"),
            "check",
            "--bundle",
            str(forged),
            *_enablement_args(art),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "REJECTED" in out
