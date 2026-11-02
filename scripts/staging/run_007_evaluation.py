#!/usr/bin/env python3
"""Operator driver for the Spec 007 evaluation and enablement chain.

Each subcommand reads the previous step's JSON artifact from one directory and
writes the next, sealed by the library exactly as the in-repo functions do:

    freeze          pilot manifest            -> corpus.json      (CorpusFreeze)
    run             corpus.json + run inputs  -> run.json         (BaselineRun)
    propose         run.json                  -> proposal.json    (ThresholdProposal)
    approve         proposal.json             -> approval.json    (OperatorApproval)
    enable-staging  approval.json + run.json  -> staging.json     (StagingEnablement)
    pin             all of the above          -> receipt.json     (EvaluationEnablementReceipt)
    sign            receipt.json + key file   -> signature.json   (ReceiptSignature)
    verify          receipt.json + signature  -> PASS / FAIL codes

One chain covers exactly one provider (``enable_staging`` requires
``providers == (assisted_provider_id,)``), so ``--provider`` is global and the
default directory is ``backend/intelligence/enablement/<provider>/``. Files under
``backend/`` ship in the staging image (``backend/x`` becomes ``/app/x``).

Nothing here weakens a library check: every refusal is printed with its stable
code and the command exits 1. Artifacts are never overwritten. Credentials come
from the environment (``core.config.Settings``) and are never printed. The signing
key is read from a file path; it is never taken from argv or an environment value.

``run --dry-run`` uses the fixture provider with operator-supplied packets so the
chain can be exercised offline. A dry-run directory carries a ``DRY_RUN`` marker,
must be outside ``backend/`` and is never evidence.

Usage (repo root, backend venv):
  python scripts/staging/run_007_evaluation.py --provider nvidia freeze \\
      --manifest fixtures/vision_eval/pilot-manifest.json
  python scripts/staging/run_007_evaluation.py --provider nvidia run \\
      --inputs ~/patchhive-corpus/run-inputs.json --harness-sha "$(git rev-parse HEAD)"
  ... propose | approve | enable-staging | pin | sign | verify
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence, TypeVar

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from pydantic import BaseModel, ValidationError  # noqa: E402

from core.config import Settings  # noqa: E402
from intelligence.clef_evaluation import LabeledCorpusCase, Modality  # noqa: E402
from intelligence.clef_provider import ClefImage, ClefProviderError  # noqa: E402
from intelligence.contracts import (  # noqa: E402
    ChoiceOption,
    ChoiceRequest,
    DecisionPacket,
    DecisionPurpose,
    stable_sha256,
)
from intelligence.enablement_gate import enablement_gate_failures  # noqa: E402
from intelligence.evaluation_corpus import (  # noqa: E402
    CorpusFreeze,
    CorpusFreezeError,
    freeze_corpus,
    verify_corpus_freeze,
)
from intelligence.evaluation_enablement import (  # noqa: E402
    BaselineRun,
    EnablementChain,
    EnablementError,
    EvaluationEnablementReceipt,
    OperatorApproval,
    StagingEnablement,
    ThresholdProposal,
    approve_thresholds,
    check_frozen_thresholds,
    enable_staging,
    is_pinned_sha,
    pin_receipt,
    propose_thresholds,
    run_baseline_comparison,
    signed_enablement_receipt_failures,
)
from intelligence.fixture_provider import FixtureDecisionProvider  # noqa: E402
from intelligence.policy import DecisionPolicy, PolicyThresholds  # noqa: E402
from intelligence.receipt_signing import (  # noqa: E402
    ReceiptSignature,
    SignatureError,
    load_approver_allowlist,
    parse_utc,
    sign_receipt_sha256,
)

PROVIDERS = ("clef", "nvidia")
BASELINE_PROVIDER_ID = "fixture"
BASELINE_VERSION = "abstain-uniform.v1"
RUN_INPUTS_SCHEMA = "patchhive.eval-run-inputs.v1"
DEFAULT_QUESTION = (
    "Which Eurorack module is shown in the evidence? Answer none_of_above when it is "
    "not one of the options."
)
DRY_RUN_MARKER = "DRY_RUN"

CORPUS = "corpus.json"
RUN = "run.json"
PROPOSAL = "proposal.json"
APPROVAL = "approval.json"
STAGING = "staging.json"
RECEIPT = "receipt.json"
SIGNATURE = "signature.json"

_M = TypeVar("_M", bound=BaseModel)


class Refused(Exception):
    """A fail-closed refusal. ``code`` is stable; nothing secret is ever put in it."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


# ---------------------------------------------------------------------------
# Artifact I/O
# ---------------------------------------------------------------------------


def _out(message: str) -> None:
    print(message, flush=True)


def _under_backend(path: Path) -> bool:
    try:
        path.resolve().relative_to(BACKEND.resolve())
    except ValueError:
        return False
    return True


def container_path(path: Path) -> str | None:
    """The path the staging container sees for a file under ``backend/`` (``/app/...``)."""
    if not _under_backend(path):
        return None
    return "/app/" + path.resolve().relative_to(BACKEND.resolve()).as_posix()


def _read_json(path: Path, code: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Refused(f"{code}_MISSING", str(path)) from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refused(f"{code}_UNREADABLE", str(path)) from exc


def _load(directory: Path, name: str, model: type[_M]) -> _M:
    code = "ARTIFACT_" + name.split(".")[0].upper()
    raw = _read_json(directory / name, code)
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise Refused(f"{code}_INVALID", str(directory / name)) from exc


def _write(directory: Path, name: str, record: BaseModel) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    payload = record.model_dump_json(indent=2) + "\n"
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise Refused("ARTIFACT_EXISTS", f"{target} (artifacts are never overwritten; move it away first)") from exc
    _out(f"wrote {target}")
    return target


def _is_dry_run(directory: Path) -> bool:
    return (directory / DRY_RUN_MARKER).exists()


def _dry_run_banner(directory: Path) -> None:
    if _is_dry_run(directory):
        _out("DRY RUN: fixture-provider artifacts. Not evidence; never commit, sign for staging or deploy.")


# ---------------------------------------------------------------------------
# Run inputs (candidates and local images; the manifest holds hashes only)
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_hash(recorded: str, computed_hex: str) -> bool:
    return recorded in (computed_hex, "sha256:" + computed_hex)


def _content_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise Refused("IMAGE_TYPE_UNSUPPORTED", "only PNG, JPEG and WebP images can be sent")


def _load_inputs(path: Path) -> tuple[dict[str, Any], Path]:
    data = _read_json(path, "RUN_INPUTS")
    if not isinstance(data, dict) or data.get("schema_version") != RUN_INPUTS_SCHEMA:
        raise Refused("RUN_INPUTS_SCHEMA", f"schema_version must be {RUN_INPUTS_SCHEMA}")
    if not isinstance(data.get("cases"), dict) or not data["cases"]:
        raise Refused("RUN_INPUTS_EMPTY")
    return data, path.resolve().parent


def _choice_options(case_id: str, entry: Any) -> tuple[ChoiceOption, ...]:
    raw = entry.get("candidates") if isinstance(entry, dict) else None
    if not isinstance(raw, list) or not raw:
        raise Refused("CANDIDATES_MISSING", case_id)
    try:
        return tuple(
            ChoiceOption(choice_id=item) if isinstance(item, str) else ChoiceOption.model_validate(item)
            for item in raw
        )
    except ValidationError as exc:
        raise Refused("CANDIDATES_INVALID", case_id) from exc


def candidate_set_hash(options: Sequence[ChoiceOption]) -> str:
    """The hash a module-identity ChoiceRequest computes for these exact options."""
    return "sha256:" + stable_sha256(tuple(options))


def _evidence_hash(case_id: str, image_hashes: Sequence[str]) -> str:
    return stable_sha256({"case_id": case_id, "image_asset_hashes": list(image_hashes)})


class _PreparedCase:
    def __init__(self, case_id: str, request: ChoiceRequest, options: tuple[ChoiceOption, ...],
                 images: tuple[Path, ...], image_hex: tuple[str, ...]) -> None:
        self.case_id = case_id
        self.request = request
        self.options = options
        self.images = images
        self.image_hex = image_hex


def _prepare_cases(corpus: CorpusFreeze, inputs: dict[str, Any], base: Path) -> dict[str, _PreparedCase]:
    """Bind every frozen case to its candidates and local image files, failing closed."""
    index = corpus.case_index()
    given = inputs["cases"]
    if set(given) != set(index):
        missing = sorted(set(index) - set(given))
        extra = sorted(set(given) - set(index))
        raise Refused("RUN_INPUTS_NOT_FROZEN_CORPUS", f"missing={missing[:5]} extra={extra[:5]}")
    question = inputs.get("question") or DEFAULT_QUESTION
    prepared: dict[str, _PreparedCase] = {}
    for case_id in sorted(index):
        frozen = index[case_id]
        entry = given[case_id]
        options = _choice_options(case_id, entry)
        ids = {item.choice_id for item in options}
        if "none_of_above" not in ids:
            raise Refused("CANDIDATES_WITHOUT_NONE_OF_ABOVE", case_id)
        if frozen.expected_choice not in ids:
            raise Refused("CANDIDATES_WITHOUT_EXPECTED_CHOICE", case_id)
        computed = stable_sha256(tuple(options))
        if not _same_hash(frozen.candidate_set_hash, computed):
            raise Refused(
                "CANDIDATE_SET_HASH_MISMATCH",
                f"{case_id}: frozen {frozen.candidate_set_hash}, inputs hash to sha256:{computed}",
            )
        images: list[Path] = []
        image_hex: list[str] = []
        for raw in entry.get("images") or []:
            image_path = (base / str(raw)).resolve()
            if not image_path.is_file():
                raise Refused("IMAGE_FILE_MISSING", f"{case_id}: {raw}")
            digest = _sha256_file(image_path)
            if digest not in frozen.image_sha256_hex():
                raise Refused("IMAGE_NOT_IN_FROZEN_CORPUS", f"{case_id}: {raw}")
            images.append(image_path)
            image_hex.append(digest)
        context = entry.get("context") or {}
        if not isinstance(context, dict):
            raise Refused("CONTEXT_INVALID", case_id)
        request = ChoiceRequest(
            request_id=f"eval007-{case_id}",
            purpose=DecisionPurpose.module_identity,
            evidence_hash=_evidence_hash(case_id, frozen.image_asset_hashes),
            context=context,
            idempotency_key=f"eval007:{corpus.corpus_sha256[:16]}:{case_id}",
            question=question,
            choices=options,
        )
        prepared[case_id] = _PreparedCase(case_id, request, options, tuple(images), tuple(image_hex))
    return prepared


def _labeled(corpus: CorpusFreeze, case: _PreparedCase, packet: DecisionPacket) -> LabeledCorpusCase:
    frozen = corpus.case_index()[case.case_id]
    vision = bool(case.image_hex)
    return LabeledCorpusCase(
        case_id=frozen.case_id,
        cohort=frozen.cohort,
        modality=Modality.vision if vision else Modality.text,
        expected_choice=frozen.expected_choice,
        licensed_source=f"frozen-corpus:{corpus.corpus_sha256}",
        packet=packet,
        candidate_options=case.options,
        image_sha256=case.image_hex[0] if vision else None,
    )


def _abstain_packet(request: ChoiceRequest) -> DecisionPacket:
    """Deterministic baseline: no model, uniform over the candidates, selects none_of_above."""
    ids = [item.choice_id for item in request.choices]
    share = 1.0 / len(ids)
    return DecisionPacket(
        decision_id=f"{BASELINE_PROVIDER_ID}-{request.request_id}",
        request_id=request.request_id,
        provider=BASELINE_PROVIDER_ID,
        provider_version=BASELINE_VERSION,
        evidence_hash=request.evidence_hash,
        answer_type="choice",
        selected_choice="none_of_above",
        probabilities={choice_id: share for choice_id in ids},
        confidence=share,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=datetime.now(timezone.utc),
    )


def _fixture_packet(provider: str, request: ChoiceRequest, raw: Any) -> DecisionPacket:
    if not isinstance(raw, dict):
        raise Refused("FIXTURE_PACKET_INVALID", request.request_id)
    try:
        return DecisionPacket(
            decision_id=f"dry-run-{provider}-{request.request_id}",
            request_id=request.request_id,
            provider=provider,
            provider_version="dry-run-fixture",
            evidence_hash=request.evidence_hash,
            answer_type="choice",
            selected_choice=raw.get("selected_choice"),
            probabilities=raw.get("probabilities") or {},
            confidence=raw.get("confidence"),
            candidate_set_hash=request.candidate_set_hash(),
            created_at=datetime.now(timezone.utc),
        )
    except ValidationError as exc:
        raise Refused("FIXTURE_PACKET_INVALID", request.request_id) from exc


def _live_provider(provider: str, settings: Settings, image_loader: Callable[[Any], Sequence[ClefImage]]):
    """Build the configured provider from env-backed settings. Refuses unless it is enabled."""
    if provider == "nvidia":
        if not settings.enable_nvidia_provider:
            raise Refused("PROVIDER_FLAG_OFF", "set ENABLE_NVIDIA_PROVIDER=true in this shell")
        if not settings.nvidia_api_key:
            raise Refused("PROVIDER_CREDENTIALS_MISSING", "NVIDIA_API_KEY is not set in this shell")
        from intelligence.nvidia_provider import NvidiaVisionProvider

        return NvidiaVisionProvider(
            enabled=True,
            api_key=settings.nvidia_api_key,
            model=settings.nvidia_model,
            base_url=settings.nvidia_base_url,
            timeout_seconds=settings.nvidia_timeout_seconds,
            image_loader=image_loader,
        )
    if not settings.enable_clef_provider:
        raise Refused("PROVIDER_FLAG_OFF", "set ENABLE_CLEF_PROVIDER=true in this shell")
    if not settings.cloudflare_account_id or not settings.cloudflare_ai_api_token:
        raise Refused(
            "PROVIDER_CREDENTIALS_MISSING",
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AI_API_TOKEN must be set in this shell",
        )
    from intelligence.clef_provider import ClefDecisionProvider

    return ClefDecisionProvider(
        enabled=True,
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_ai_api_token,
        model=settings.clef_model,
        base_url=settings.clef_base_url,
        timeout_seconds=settings.clef_timeout_seconds,
        image_loader=image_loader,
    )


def _policy(settings: Settings) -> DecisionPolicy:
    return DecisionPolicy(
        PolicyThresholds(
            policy_version=settings.decision_policy_version,
            auto_propose_at=settings.decision_auto_propose_at,
            user_review_at=settings.decision_user_review_at,
            probability_margin=settings.decision_probability_margin,
        )
    )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_freeze(args: argparse.Namespace) -> None:
    manifest = _read_json(Path(args.manifest), "MANIFEST")
    try:
        corpus = freeze_corpus(manifest)
    except CorpusFreezeError as exc:
        raise Refused(exc.code, exc.detail) from exc
    _write(args.dir, CORPUS, corpus)
    _out(f"corpus_sha256={corpus.corpus_sha256} cases={corpus.case_count} identities={corpus.identity_count}")


def cmd_candidate_hashes(args: argparse.Namespace) -> None:
    inputs, _ = _load_inputs(Path(args.inputs))
    for case_id in sorted(inputs["cases"]):
        _out(f"{case_id} {candidate_set_hash(_choice_options(case_id, inputs['cases'][case_id]))}")


def cmd_run(args: argparse.Namespace) -> None:
    if args.dry_run:
        if _under_backend(args.dir):
            raise Refused("DRY_RUN_UNDER_BACKEND", "a dry run must write outside backend/ so it never ships")
        if not args.fixture_packets:
            raise Refused("FIXTURE_PACKETS_REQUIRED", "--dry-run needs --fixture-packets")
    elif args.fixture_packets:
        raise Refused("FIXTURE_PACKETS_WITHOUT_DRY_RUN")
    elif _is_dry_run(args.dir):
        raise Refused("DRY_RUN_DIRECTORY", "this directory holds a dry run; use a fresh one for a live run")
    if not is_pinned_sha(args.harness_sha):
        raise Refused("HARNESS_SHA_NOT_PINNED", "use the 40-hex commit the harness runs from")
    corpus = _load(args.dir, CORPUS, CorpusFreeze)
    manifest = _read_json(Path(args.manifest), "MANIFEST") if args.manifest else None
    if not verify_corpus_freeze(corpus, manifest):
        raise Refused("CORPUS_MISSING_OR_UNFROZEN", "corpus.json is tampered or no longer matches the manifest")
    inputs, base = _load_inputs(Path(args.inputs))
    prepared = _prepare_cases(corpus, inputs, base)
    settings = Settings()
    policy = _policy(settings)

    baseline_rows = []
    for case in prepared.values():
        packet = FixtureDecisionProvider({case.request.request_id: _abstain_packet(case.request)}).choose(case.request)
        baseline_rows.append(_labeled(corpus, case, packet))

    assisted_rows = []
    if args.dry_run:
        fixtures = _read_json(Path(args.fixture_packets), "FIXTURE_PACKETS")
        if not isinstance(fixtures, dict) or set(fixtures) != set(prepared):
            raise Refused("FIXTURE_PACKETS_NOT_FROZEN_CORPUS")
        for case_id, case in prepared.items():
            packet = _fixture_packet(args.provider, case.request, fixtures[case_id])
            try:
                packet = FixtureDecisionProvider({case.request.request_id: packet}).choose(case.request)
            except ValueError as exc:
                raise Refused("FIXTURE_PACKET_INVALID", case_id) from exc
            assisted_rows.append(_labeled(corpus, case, packet))
        args.dir.mkdir(parents=True, exist_ok=True)
        (args.dir / DRY_RUN_MARKER).write_text("fixture-provider dry run; not evidence\n", encoding="utf-8")
    else:
        by_request = {case.request.request_id: case for case in prepared.values()}

        def load_images(request: Any) -> Sequence[ClefImage]:
            case = by_request[request.request_id]
            loaded = []
            for path in case.images:
                data = path.read_bytes()
                loaded.append(ClefImage(content_type=_content_type(data), data=data))
            return loaded

        provider = _live_provider(args.provider, settings, load_images)
        total = len(prepared)
        for number, (case_id, case) in enumerate(prepared.items(), start=1):
            try:
                packet = provider.choose(case.request)
            except ClefProviderError as exc:
                raise Refused("PROVIDER_CALL_FAILED", f"{case_id}: {exc.code}; no run was written") from None
            assisted_rows.append(_labeled(corpus, case, packet))
            _out(f"[{number}/{total}] {case_id} answered")

    try:
        run = run_baseline_comparison(
            corpus=corpus,
            baseline_cases=baseline_rows,
            assisted_cases=assisted_rows,
            policy=policy,
            harness_sha=args.harness_sha,
            baseline_provider_id=BASELINE_PROVIDER_ID,
            assisted_provider_id=args.provider,
        )
    except EnablementError as exc:
        raise Refused(exc.code, exc.detail) from exc
    _write(args.dir, RUN, run)
    for metrics in (run.baseline, run.assisted):
        _out(
            f"{metrics.condition} ({metrics.provider_id}): top1={metrics.top1_accuracy:.4f} "
            f"topk={metrics.topk_accuracy:.4f} brier={metrics.brier_score:.4f} "
            f"ece={metrics.calibration_error:.4f} abstain={metrics.abstention_rate:.4f} "
            f"false_canon={metrics.false_canonicalization_count}"
        )
    _dry_run_banner(args.dir)


def _print_checks(run: BaselineRun, proposal: ThresholdProposal) -> bool:
    checks = check_frozen_thresholds(run.assisted, proposal.thresholds)
    for check in checks:
        verdict = "ok" if check.passed else "FAILS"
        _out(f"  {check.metric}: assisted {check.observed:.4f} {check.comparator} {check.limit:.4f} {verdict}")
    return all(check.passed for check in checks)


def cmd_propose(args: argparse.Namespace) -> None:
    _dry_run_banner(args.dir)
    run = _load(args.dir, RUN, BaselineRun)
    try:
        # 005 OQ-5 decided baseline_equal: the coded rule, thresholds equal the baseline.
        proposal = propose_thresholds(run, proposal_version=args.proposal_version)
    except EnablementError as exc:
        raise Refused(exc.code, exc.detail) from exc
    _write(args.dir, PROPOSAL, proposal)
    _out(f"rule={proposal.rule} proposal_sha256={proposal.record_sha256}")
    if not _print_checks(run, proposal):
        _out("The assisted provider does not meet these thresholds; enable-staging will refuse THRESHOLDS_NOT_MET.")


def cmd_approve(args: argparse.Namespace) -> None:
    _dry_run_banner(args.dir)
    if not args.yes_i_approve:
        raise Refused("EXPLICIT_SIGN_OFF_REQUIRED", "pass --yes-i-approve after reviewing the proposal")
    try:
        allowlist = load_approver_allowlist()
    except SignatureError as exc:
        raise Refused(exc.code) from exc
    key = allowlist.get(args.approved_by)
    if key is None:
        raise Refused("APPROVER_KEY_UNKNOWN", "--approved-by must be a key_id in evaluation_approvers.json")
    now = datetime.now(timezone.utc)
    if parse_utc(key.valid_from) > now:
        raise Refused("APPROVER_KEY_NOT_YET_VALID", args.approved_by)
    if key.revoked_at is not None and parse_utc(key.revoked_at) <= now:
        raise Refused("APPROVER_KEY_REVOKED", args.approved_by)
    proposal = _load(args.dir, PROPOSAL, ThresholdProposal)
    run = _load(args.dir, RUN, BaselineRun)
    _out(f"approving proposal {proposal.record_sha256} ({proposal.rule}):")
    _print_checks(run, proposal)
    try:
        approval = approve_thresholds(
            proposal, approved_by=args.approved_by, approved_at=now, explicit_sign_off=True
        )
    except EnablementError as exc:
        raise Refused(exc.code, exc.detail) from exc
    _write(args.dir, APPROVAL, approval)
    _out(f"approved_by={approval.approved_by} approved_at={approval.approved_at}")


def cmd_enable_staging(args: argparse.Namespace) -> None:
    _dry_run_banner(args.dir)
    approval = _load(args.dir, APPROVAL, OperatorApproval)
    run = _load(args.dir, RUN, BaselineRun)
    # Settings come from this shell; only the target environment is fixed to staging.
    # The config gates (payments off, Clef class default off, no D1) still run on them.
    try:
        staging = enable_staging(
            approval=approval,
            run=run,
            settings_obj=Settings(environment="staging"),
            target_environment="staging",
            providers=(args.provider,),
        )
    except EnablementError as exc:
        raise Refused(exc.code, exc.detail) from exc
    _write(args.dir, STAGING, staging)
    _out(f"providers={','.join(staging.providers)} staging_sha256={staging.record_sha256}")


def _print_setting(name: str, path: Path, dry_run: bool) -> None:
    if dry_run:
        _out(f"{name}: not printed for a dry run")
        return
    mapped = container_path(path)
    if mapped is None:
        _out(f"{name}: {path} is not under backend/, so it will not reach the staging container")
    else:
        _out(f"{name}={mapped}")


def cmd_pin(args: argparse.Namespace) -> None:
    dry_run = _is_dry_run(args.dir)
    _dry_run_banner(args.dir)
    try:
        receipt = pin_receipt(
            corpus=_load(args.dir, CORPUS, CorpusFreeze),
            run=_load(args.dir, RUN, BaselineRun),
            proposal=_load(args.dir, PROPOSAL, ThresholdProposal),
            approval=_load(args.dir, APPROVAL, OperatorApproval),
            staging=_load(args.dir, STAGING, StagingEnablement),
            source_commit_sha=args.source_commit_sha,
        )
    except EnablementError as exc:
        raise Refused(exc.code, exc.detail) from exc
    target = _write(args.dir, RECEIPT, receipt)
    _out(f"receipt_sha256={receipt.receipt_sha256}")
    _print_setting("DECISION_ENABLEMENT_RECEIPT_PATH", target, dry_run)


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
            raise Refused("SIGNING_KEY_UNREADABLE", "wrong password or not a PEM private key") from exc
    except ValueError as exc:
        raise Refused("SIGNING_KEY_UNREADABLE", "not a PEM private key") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise Refused("SIGNING_KEY_NOT_ED25519")
    return key


def cmd_sign(args: argparse.Namespace) -> None:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    dry_run = _is_dry_run(args.dir)
    _dry_run_banner(args.dir)
    receipt = _load(args.dir, RECEIPT, EvaluationEnablementReceipt)
    try:
        allowlist = load_approver_allowlist()
    except SignatureError as exc:
        raise Refused(exc.code) from exc
    entry = allowlist.get(receipt.approved_by)
    if entry is None:
        raise Refused("APPROVER_KEY_UNKNOWN", "the receipt's approved_by is not in evaluation_approvers.json")
    key = _read_private_key(Path(args.key).expanduser())
    public_raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    if public_raw != entry.public_key_obj().public_bytes(Encoding.Raw, PublicFormat.Raw):
        raise Refused("SIGNING_KEY_NOT_APPROVER_KEY", f"this key is not the allowlisted key for {receipt.approved_by}")
    signature = sign_receipt_sha256(key, key_id=receipt.approved_by, receipt_sha256=receipt.receipt_sha256)
    failures = signed_enablement_receipt_failures(receipt, signature, allowlist=allowlist)
    if failures:
        raise Refused("SIGNED_RECEIPT_DOES_NOT_VERIFY", ",".join(failures))
    target = _write(args.dir, SIGNATURE, signature)
    _out(f"signed receipt_sha256={receipt.receipt_sha256} key_id={signature.key_id}")
    _print_setting("DECISION_ENABLEMENT_RECEIPT_PATH", args.dir / RECEIPT, dry_run)
    _print_setting("DECISION_ENABLEMENT_SIGNATURE_PATH", target, dry_run)


def _chain(directory: Path) -> EnablementChain | None:
    names = (CORPUS, RUN, PROPOSAL, APPROVAL, STAGING)
    if not all((directory / name).exists() for name in names):
        return None
    return EnablementChain(
        corpus=_load(directory, CORPUS, CorpusFreeze),
        run=_load(directory, RUN, BaselineRun),
        proposal=_load(directory, PROPOSAL, ThresholdProposal),
        approval=_load(directory, APPROVAL, OperatorApproval),
        staging=_load(directory, STAGING, StagingEnablement),
    )


def cmd_verify(args: argparse.Namespace) -> None:
    _dry_run_banner(args.dir)
    receipt_raw = _read_json(args.dir / RECEIPT, "ARTIFACT_RECEIPT")
    signature = _load(args.dir, SIGNATURE, ReceiptSignature)
    chain = _chain(args.dir)
    failures = list(signed_enablement_receipt_failures(receipt_raw, signature, chain=chain))
    # The same check the staging container runs at startup (005 T080), on these files.
    gate = SimpleNamespace(
        environment="staging",
        decision_provider=args.provider,
        enable_decision_intelligence=True,
        decision_enablement_receipt_path=str(args.dir / RECEIPT),
        decision_enablement_signature_path=str(args.dir / SIGNATURE),
        decision_policy_version=Settings().decision_policy_version,
    )
    failures.extend(enablement_gate_failures(gate))
    failures = list(dict.fromkeys(failures))
    _out("chain replay: " + ("yes" if chain is not None else "no (chain artifacts not all present)"))
    if failures:
        raise Refused("VERIFY_FAILED", ",".join(failures))
    _out("PASS")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spec 007 evaluation and enablement driver.")
    parser.add_argument("--provider", required=True, choices=PROVIDERS, help="the one provider this chain evaluates")
    parser.add_argument(
        "--dir",
        type=Path,
        help="artifact directory (default backend/intelligence/enablement/<provider>)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("freeze", help="freeze an admitted pilot manifest into corpus.json")
    p.add_argument("--manifest", required=True)
    p.set_defaults(func=cmd_freeze)

    p = sub.add_parser("candidate-hashes", help="print each case's candidate_set_hash from a run-inputs file")
    p.add_argument("--inputs", required=True)
    p.set_defaults(func=cmd_candidate_hashes)

    p = sub.add_parser("run", help="baseline vs provider on the frozen corpus -> run.json")
    p.add_argument("--inputs", required=True, help="run-inputs JSON: candidates and local image paths per case")
    p.add_argument("--harness-sha", required=True, help="the 40-hex commit the harness runs from")
    p.add_argument("--manifest", help="also check corpus.json still matches this manifest")
    p.add_argument("--dry-run", action="store_true", help="fixture provider instead of a live call")
    p.add_argument("--fixture-packets", help="dry run only: {case_id: {selected_choice, probabilities}}")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("propose", help="propose thresholds (baseline_equal) -> proposal.json")
    p.add_argument("--proposal-version", required=True)
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("approve", help="record the operator approval -> approval.json")
    p.add_argument("--approved-by", required=True, help="your key_id in evaluation_approvers.json")
    p.add_argument("--yes-i-approve", action="store_true", help="explicit sign-off on the exact proposal")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("enable-staging", help="staging-only authorization record -> staging.json")
    p.set_defaults(func=cmd_enable_staging)

    p = sub.add_parser("pin", help="pin the receipt -> receipt.json")
    p.add_argument("--source-commit-sha", required=True)
    p.set_defaults(func=cmd_pin)

    p = sub.add_parser("sign", help="sign receipt_sha256 with the approver key file -> signature.json")
    p.add_argument("--key", required=True, help="path to the Ed25519 private key PEM (never the key itself)")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("verify", help="verify receipt + signature against the committed allowlist")
    p.set_defaults(func=cmd_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dir is None:
        args.dir = BACKEND / "intelligence" / "enablement" / args.provider
    args.dir = Path(os.path.expanduser(str(args.dir)))
    try:
        args.func(args)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
