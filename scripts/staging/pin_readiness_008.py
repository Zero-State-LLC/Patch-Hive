#!/usr/bin/env python3
"""Spec 008 T050b and T072 driver: pin the readiness docs to the walkthrough SHA, then
replay the five cutover events to BETA_ELIGIBLE.

The walkthrough bundle is the JSON that ``design_engine_walkthrough.py`` writes
(``--receipt-out``): alias evidence, FE cutover, walkthrough start and receipt. The
signed spec 007 receipt and its signature come from ``run_007_evaluation.py``
(``receipt.json`` and ``signature.json``).

Commands:
    check   bundle [+ 007 receipt and signature]   -> what still blocks the pin (no key)
    pin     bundle + 007 receipt and signature + key -> readiness-pin.json (signed)
    replay  bundle + readiness-pin.json            -> exit 0 only at BETA_ELIGIBLE

    python scripts/staging/pin_readiness_008.py check \\
        --bundle docs/evidence/receipts/staging-design-walkthrough-<date>.json
    python scripts/staging/pin_readiness_008.py pin --bundle <bundle> \\
        --enablement-receipt <dir>/receipt.json --enablement-signature <dir>/signature.json \\
        --key ~/patchhive-approver/approver-2026-11.pem --pinned-by approver-2026-11 \\
        --out docs/evidence/receipts/readiness-pin-<date>.json
    python scripts/staging/pin_readiness_008.py replay --bundle <bundle> --pin <pin.json>

The private key never leaves the operator's machine; this script only reads it to sign.
It writes nothing except ``--out``, and changes no setting, route, DNS or payment flag.
"""

from __future__ import annotations

import argparse
import getpass
import json
import stat
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from pydantic import ValidationError  # noqa: E402

from core.ops.f5_cutover import (  # noqa: E402
    REQUIRED_PIN_DOCUMENTS,
    AliasParityEvidence,
    CutoverError,
    CutoverEvent,
    CutoverEventType as E,
    CutoverMachine,
    FeCutoverEvidence,
    ReadinessPin,
    WalkthroughReceipt,
    WalkthroughStart,
    beta_eligible,
    pin_readiness_docs,
    replay,
)
from intelligence.evaluation_enablement import (  # noqa: E402
    EvaluationEnablementReceipt,
    signed_enablement_receipt_failures,
)
from intelligence.receipt_signing import (  # noqa: E402
    ReceiptSignature,
    SignatureError,
    load_approver_allowlist,
)


class Refused(Exception):
    """A step that cannot proceed; ``code`` is stable and carries no secret."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _out(message: str) -> None:
    print(message, flush=True)


def _read_json(path: Path, code: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refused(code, str(path)) from exc


def load_bundle(path: Path) -> dict[str, Any]:
    """The four walkthrough artifacts, validated as sealed records."""
    raw = _read_json(path, "BUNDLE_UNREADABLE")
    try:
        return {
            "alias": AliasParityEvidence.model_validate(raw["alias_evidence"]),
            "fe": FeCutoverEvidence.model_validate(raw["fe_cutover"]),
            "start": WalkthroughStart.model_validate(raw["walkthrough_start"]),
            "receipt": WalkthroughReceipt.model_validate(raw["receipt"]),
        }
    except (KeyError, ValidationError) as exc:
        raise Refused("BUNDLE_INVALID", str(exc).splitlines()[0]) from exc


def load_enablement(receipt_path: Path | None, signature_path: Path | None):
    if receipt_path is None or signature_path is None:
        return None, None
    try:
        receipt = EvaluationEnablementReceipt.model_validate(
            _read_json(receipt_path, "ENABLEMENT_RECEIPT_UNREADABLE")
        )
        signature = ReceiptSignature.model_validate(
            _read_json(signature_path, "ENABLEMENT_SIGNATURE_UNREADABLE")
        )
    except ValidationError as exc:
        raise Refused("ENABLEMENT_INVALID", str(exc).splitlines()[0]) from exc
    return receipt, signature


def events(
    bundle: dict[str, Any], pin: ReadinessPin | None = None
) -> list[CutoverEvent]:
    out = [
        CutoverEvent(E.EXPOSE_CANON_ALIAS, alias=bundle["alias"]),
        CutoverEvent(E.SWITCH_FE_LIST, fe_cutover=bundle["fe"]),
        CutoverEvent(E.RUN_WALKTHROUGH, start=bundle["start"]),
        CutoverEvent(E.CAPTURE_RECEIPT, receipt=bundle["receipt"]),
    ]
    if pin is not None:
        out.append(CutoverEvent(E.OPERATOR_PIN, pin=pin))
    return out


def _print_history(machine: CutoverMachine) -> None:
    for step in machine.history:
        verdict = "accepted" if step.accepted else "REJECTED " + ",".join(step.reasons)
        _out(
            f"  {step.event.value:<20} {step.from_state.value} -> {step.to_state.value}  {verdict}"
        )
    _out(f"state: {machine.state.value}")


def documents(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for rel in REQUIRED_PIN_DOCUMENTS:
        path = root / rel
        if path.exists():
            found[rel] = path.read_text(encoding="utf-8")
    return found


def unresolved_p0(path: Path | None) -> list[str]:
    if path is None:
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_private_key(path: Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    try:
        mode = path.stat().st_mode
        data = path.read_bytes()
    except OSError as exc:
        raise Refused("SIGNING_KEY_UNREADABLE", str(path)) from exc
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        _out(f"warning: {path} is readable by group or others; chmod 600 it")
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except TypeError:
        password = getpass.getpass("Key password: ").encode("utf-8")
        try:
            key = serialization.load_pem_private_key(data, password=password)
        except (TypeError, ValueError) as exc:
            raise Refused(
                "SIGNING_KEY_UNREADABLE", "wrong password or not a PEM private key"
            ) from exc
    except ValueError as exc:
        raise Refused("SIGNING_KEY_UNREADABLE", "not a PEM private key") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise Refused("SIGNING_KEY_NOT_ED25519")
    return key


def cmd_check(args: argparse.Namespace) -> int:
    """Everything that would stop the pin, without needing the key."""
    bundle = load_bundle(args.bundle)
    receipt: WalkthroughReceipt = bundle["receipt"]
    blockers: list[str] = []

    _out(
        f"walkthrough receipt {receipt.record_sha256[:12]}… at source {receipt.source_commit_sha}"
    )
    machine = replay(events(bundle))
    _print_history(machine)
    if machine.state.value != "RECEIPT_CAPTURED":
        blockers.append(
            "the walkthrough artifacts do not replay to RECEIPT_CAPTURED (see REJECTED above); re-run the walkthrough"
        )

    docs = documents(args.root)
    for rel in REQUIRED_PIN_DOCUMENTS:
        if rel not in docs:
            blockers.append(f"{rel} is missing")
        elif receipt.source_commit_sha not in docs[rel]:
            blockers.append(
                f"{rel} does not cite the walkthrough source SHA {receipt.source_commit_sha}"
            )

    enablement, signature = load_enablement(
        args.enablement_receipt, args.enablement_signature
    )
    if enablement is None:
        blockers.append("no signed spec 007 receipt yet (007 T060b, T083)")
    else:
        try:
            failures = signed_enablement_receipt_failures(
                enablement, signature, allowlist=load_approver_allowlist()
            )
        except SignatureError as exc:
            failures = (exc.code,)
        if failures:
            blockers.append("the 007 receipt does not verify: " + ",".join(failures))

    p0 = unresolved_p0(args.unresolved_p0)
    if p0:
        blockers.append("open P0 regressions: " + ", ".join(p0))

    if blockers:
        _out("blocked:")
        for item in blockers:
            _out(f"  - {item}")
        return 1
    _out("ready to pin")
    return 0


def cmd_pin(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.bundle)
    enablement, signature = load_enablement(
        args.enablement_receipt, args.enablement_signature
    )
    if enablement is None:
        raise Refused(
            "ENABLEMENT_RECEIPT_MISSING",
            "pass --enablement-receipt and --enablement-signature",
        )
    key = _read_private_key(Path(args.key).expanduser())
    try:
        pin = pin_readiness_docs(
            receipt=bundle["receipt"],
            documents=documents(args.root),
            unresolved_p0=unresolved_p0(args.unresolved_p0),
            enablement_receipt=enablement,
            enablement_signature=signature,
            pinned_by=args.pinned_by,
            signing_key=key,
        )
    except CutoverError as exc:
        raise Refused(exc.code, exc.detail) from exc
    machine = replay(events(bundle, pin))
    if not beta_eligible(machine):
        _print_history(machine)
        raise Refused("PIN_DOES_NOT_REACH_BETA_ELIGIBLE")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(pin.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _out(f"pinned {pin.record_sha256} by {pin.pinned_by} -> {args.out}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.bundle)
    try:
        pin = ReadinessPin.model_validate(_read_json(args.pin, "PIN_UNREADABLE"))
    except ValidationError as exc:
        raise Refused("PIN_INVALID", str(exc).splitlines()[0]) from exc
    machine = replay(events(bundle, pin))
    _print_history(machine)
    eligible = beta_eligible(machine)
    _out(f"beta_eligible: {eligible}")
    return 0 if eligible else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repo root holding the readiness docs",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--bundle", type=Path, required=True, help="walkthrough receipt bundle JSON"
        )

    def enablement(p: argparse.ArgumentParser, required: bool) -> None:
        p.add_argument("--enablement-receipt", type=Path, required=required)
        p.add_argument("--enablement-signature", type=Path, required=required)
        p.add_argument(
            "--unresolved-p0",
            type=Path,
            help="file listing open P0 regressions, one per line",
        )

    check = sub.add_parser("check", help="what still blocks the pin (no key needed)")
    common(check)
    enablement(check, required=False)
    check.set_defaults(func=cmd_check)

    pin = sub.add_parser("pin", help="sign the readiness pin with the approver key")
    common(pin)
    enablement(pin, required=True)
    pin.add_argument(
        "--key", required=True, help="the approver's Ed25519 PEM private key"
    )
    pin.add_argument(
        "--pinned-by", required=True, help="the approver key id, e.g. approver-2026-11"
    )
    pin.add_argument("--out", type=Path, required=True)
    pin.set_defaults(func=cmd_pin)

    rep = sub.add_parser(
        "replay", help="replay the five events; exit 0 only at BETA_ELIGIBLE"
    )
    common(rep)
    rep.add_argument("--pin", type=Path, required=True)
    rep.set_defaults(func=cmd_replay)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Refused as exc:
        _out(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
