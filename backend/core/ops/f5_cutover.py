"""Spec 008: dual-path F5 cutover and Design Engine staging receipt gate.

State machine (specs/008-dual-path-f5-design-receipts/tasks.md):

    INVENTORY_LEGACY -> F5_ALIAS_LIVE -> FE_CUTOVER -> WALKTHROUGH_PENDING
        -> RECEIPT_CAPTURED -> BETA_ELIGIBLE

Every artifact is a frozen pydantic record sealed by ``record_sha256``. Guards
re-verify integrity and SHA links; a rejected event is recorded with reasons and
leaves the state unchanged. No path reaches BETA_ELIGIBLE without a captured
walkthrough receipt, and production payments must stay disabled throughout.

This module only *evaluates* evidence. It never mutates settings, routing, DNS,
or payment configuration. Records carry hashes, flags, and outcomes only: no
passwords, tokens, database URLs, or pack bytes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Literal, Mapping, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from intelligence.contracts import stable_sha256
from intelligence.evaluation_enablement import (
    EvaluationEnablementReceipt,
    is_pinned_sha,
    verify_enablement_receipt,
)

ALIAS_EVIDENCE_SCHEMA = "patchhive.f5-alias-evidence.v1"
FE_CUTOVER_SCHEMA = "patchhive.f5-fe-cutover.v1"
SEED_AUTH_SCHEMA = "patchhive.seed-auth-check.v1"
WALKTHROUGH_START_SCHEMA = "patchhive.design-walkthrough-start.v1"
WALKTHROUGH_RECEIPT_SCHEMA = "patchhive.design-walkthrough-receipt.v1"
READINESS_PIN_SCHEMA = "patchhive.readiness-pin.v1"

CANON_LIST_ROUTE = ("GET", "/api/canon/rigs")
CANON_DETAIL_ROUTE = ("GET", "/api/canon/rigs/{rig_id}")
LEGACY_LIST_ROUTE = ("GET", "/api/racks/")

# F2 read aliases plus the F4 evidence dual-mounts (docs/evidence/F4_CANON_EVIDENCE_ALIASES.md).
REQUIRED_ALIAS_ROUTES: tuple[tuple[str, str], ...] = (
    CANON_LIST_ROUTE,
    CANON_DETAIL_ROUTE,
    ("GET", "/api/canon/rigs/{rack_id}/evidence/images"),
    ("POST", "/api/canon/rigs/{rack_id}/evidence/images"),
    ("DELETE", "/api/canon/rigs/{rack_id}/evidence/images/{asset_id}"),
    ("GET", "/api/canon/rigs/{rack_id}/evidence/candidates"),
    ("GET", "/api/canon/rigs/{rack_id}/evidence/reconcile"),
    ("GET", "/api/canon/rigs/{rack_id}/evidence/inventory"),
    ("POST", "/api/canon/rigs/{rack_id}/evidence/confirmations"),
)

# Existing generate and confirmation gates that the FE cutover must leave intact.
REQUIRED_GATE_ROUTES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/patches/generate/{rack_id}"),
    ("POST", "/api/racks/{rack_id}/evidence/confirmations"),
    ("POST", "/api/canon/rigs/{rack_id}/evidence/confirmations"),
)

# Active inventory list pages that must read the canon alias (T020).
REQUIRED_FE_LIST_PAGES: tuple[str, ...] = (
    "frontend/src/pages/Racks.tsx",
    "frontend/src/pages/Modules.tsx",
)

CANON_RIGS_PREFIX = "/api/canon/rigs"
LEGACY_RACKS_PREFIX = "/api/racks"
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_LEGACY_LIST_CALL = re.compile(r"\brackApi\.list\s*\(")
_CANON_LIST_CALL = re.compile(r"\bcanonApi\.listRigs\s*\(")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class CutoverError(ValueError):
    """Fail-closed error. ``code`` is stable and never contains secrets."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


_R = TypeVar("_R", bound="_Sealed")


class _Sealed(BaseModel):
    """Frozen record whose ``record_sha256`` seals every other field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def content_sha256(self) -> str:
        return stable_sha256(self.model_dump(mode="json", exclude={"record_sha256"}))

    def sealed(self: _R) -> _R:
        return self.model_copy(update={"record_sha256": self.content_sha256()})

    def intact(self) -> bool:
        stored = getattr(self, "record_sha256", "")
        return bool(stored) and stored == self.content_sha256()


def _route_label(route: tuple[str, str]) -> str:
    return f"{route[0]} {route[1]}"


def route_table(openapi: Mapping[str, Any]) -> frozenset[tuple[str, str]]:
    """(METHOD, path) pairs from an OpenAPI document (``app.openapi()``)."""
    pairs: set[tuple[str, str]] = set()
    for path, ops in (openapi.get("paths") or {}).items():
        for method in ops or {}:
            upper = str(method).upper()
            if upper in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                pairs.add((upper, str(path)))
    return frozenset(pairs)


def _ids_sha256(ids: Iterable[int]) -> str:
    return stable_sha256(sorted({int(value) for value in ids}))


# ---------------------------------------------------------------------------
# T010 canonical inventory list alias
# ---------------------------------------------------------------------------


class AliasParityEvidence(_Sealed):
    schema_version: str = ALIAS_EVIDENCE_SCHEMA
    missing_alias_routes: tuple[str, ...]
    rig_count: int = Field(ge=0)
    legacy_ids_sha256: str
    canon_ids_sha256: str
    same_set: bool
    canon_write_routes: tuple[str, ...]
    new_write_surface: tuple[str, ...]
    record_sha256: str = ""


def collect_alias_evidence(
    routes: Iterable[tuple[str, str]],
    *,
    legacy_ids: Iterable[int],
    canon_ids: Iterable[int],
) -> AliasParityEvidence:
    """Compare the canon list alias to the legacy list and audit write surface.

    ``legacy_ids`` / ``canon_ids`` are the full (unpaginated) id sets returned by
    ``GET /api/racks/`` and ``GET /api/canon/rigs``. A write route under the canon
    prefix counts as *new* surface unless the same method exists on the legacy
    ``/api/racks`` twin path (i.e. it is a dual-mount alias, not a new writer).
    """
    table = frozenset(routes)
    legacy = sorted({int(value) for value in legacy_ids})
    canon = sorted({int(value) for value in canon_ids})
    missing = tuple(_route_label(r) for r in REQUIRED_ALIAS_ROUTES if r not in table)
    canon_writes = sorted(
        r for r in table if r[0] in _WRITE_METHODS and r[1].startswith(CANON_RIGS_PREFIX)
    )
    new_surface: list[str] = []
    for method, path in canon_writes:
        twin = (method, LEGACY_RACKS_PREFIX + path[len(CANON_RIGS_PREFIX):])
        if twin not in table:
            new_surface.append(_route_label((method, path)))
    record = AliasParityEvidence(
        missing_alias_routes=missing,
        rig_count=len(canon),
        legacy_ids_sha256=_ids_sha256(legacy),
        canon_ids_sha256=_ids_sha256(canon),
        same_set=legacy == canon,
        canon_write_routes=tuple(_route_label(r) for r in canon_writes),
        new_write_surface=tuple(new_surface),
    )
    return record.sealed()


# ---------------------------------------------------------------------------
# T020 frontend list cutover
# ---------------------------------------------------------------------------


class DualWriteAudit(BaseModel):
    """F3 dual-write invariants observed on one generate response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    failures: tuple[str, ...]


def audit_generate_dual_write(body: Mapping[str, Any]) -> DualWriteAudit:
    """Check a ``POST /api/patches/generate/{rack_id}`` response for F3 dual-write.

    Native bridge ids, 64-hex manifest hash, a sealed inventory revision, and no
    invented ``legacy-*`` ids (docs/evidence/F3_GENERATE_DUAL_WRITE_AUDIT.md).
    """
    failures: list[str] = []
    if body.get("export_bridge_ready") is not True:
        failures.append("EXPORT_BRIDGE_NOT_READY")
    if not str(body.get("source_run_id") or "").startswith("gen-run-"):
        failures.append("SOURCE_RUN_NOT_NATIVE")
    if not str(body.get("rig_revision_id") or "").startswith("rig-rev-"):
        failures.append("RIG_REVISION_NOT_NATIVE")
    if not _HEX64.match(str(body.get("artifact_manifest_hash") or "")):
        failures.append("MANIFEST_HASH_INVALID")
    if not str(body.get("inventory_revision_id") or "").startswith("inv-rev-"):
        failures.append("INVENTORY_REVISION_MISSING")
    for key in ("source_run_id", "rig_revision_id", "inventory_revision_id"):
        if str(body.get(key) or "").startswith("legacy-"):
            failures.append(f"LEGACY_ID_INVENTED:{key}")
    return DualWriteAudit(passed=not failures, failures=tuple(failures))


def scan_fe_list_callers(sources: Mapping[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (files still calling ``rackApi.list``, files calling ``canonApi.listRigs``)."""
    legacy = tuple(sorted(name for name, text in sources.items() if _LEGACY_LIST_CALL.search(text)))
    canon = tuple(sorted(name for name, text in sources.items() if _CANON_LIST_CALL.search(text)))
    return legacy, canon


class FeCutoverEvidence(_Sealed):
    schema_version: str = FE_CUTOVER_SCHEMA
    alias_evidence_sha256: str
    fe_list_route: str = _route_label(CANON_LIST_ROUTE)
    fe_detail_route: str = _route_label(CANON_DETAIL_ROUTE)
    scanned_files: tuple[str, ...]
    legacy_list_callers: tuple[str, ...]
    canon_list_callers: tuple[str, ...]
    missing_gate_routes: tuple[str, ...]
    dual_write: DualWriteAudit
    record_sha256: str = ""


def collect_fe_cutover_evidence(
    alias: AliasParityEvidence,
    routes: Iterable[tuple[str, str]],
    *,
    fe_sources: Mapping[str, str],
    generate_response: Mapping[str, Any],
) -> FeCutoverEvidence:
    """Evidence that active FE inventory list pages read the canon alias only."""
    if not alias.intact():
        raise CutoverError("ALIAS_EVIDENCE_TAMPERED")
    table = frozenset(routes)
    legacy, canon = scan_fe_list_callers(fe_sources)
    record = FeCutoverEvidence(
        alias_evidence_sha256=alias.record_sha256,
        scanned_files=tuple(sorted(fe_sources)),
        legacy_list_callers=legacy,
        canon_list_callers=canon,
        missing_gate_routes=tuple(_route_label(r) for r in REQUIRED_GATE_ROUTES if r not in table),
        dual_write=audit_generate_dual_write(generate_response),
    )
    return record.sealed()


def fe_cutover_failures(fe: FeCutoverEvidence) -> tuple[str, ...]:
    """Content checks shared by ``start_walkthrough`` and the switch_fe_list guard."""
    failed: list[str] = []
    if fe.legacy_list_callers or not fe.canon_list_callers:
        failed.append("FE_LIST_NOT_ON_CANON_ALIAS")
    if any(page not in fe.canon_list_callers for page in REQUIRED_FE_LIST_PAGES):
        failed.append("FE_LIST_PAGE_NOT_CUT_OVER")
    if not fe.dual_write.passed:
        failed.append("DUAL_WRITE_REGRESSION")
    if fe.missing_gate_routes:
        failed.append("GENERATE_OR_CONFIRMATION_GATE_CHANGED")
    return tuple(failed)


# ---------------------------------------------------------------------------
# T030 seed authentication alignment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedAccount:
    """A seeded demo account. The password is used for verification only and is
    never written into any record."""

    username: str
    password: str = field(repr=False)
    role: str


class SeedAccountStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    username: str
    expected_role: str
    exists: bool
    password_matches: bool
    role_matches: bool


class SeedAuthCheck(_Sealed):
    schema_version: str = SEED_AUTH_SCHEMA
    accounts: tuple[SeedAccountStatus, ...]
    aligned: bool
    record_sha256: str = ""


def check_seed_auth(db: Any, accounts: Iterable[SeedAccount]) -> SeedAuthCheck:
    """Verify each seeded account exists with the seeded password and role.

    Read-only: never creates users or rewrites password hashes (that is the
    seeder's job, so the walkthrough needs no manual credential patching).
    """
    from community.models import User
    from core.security import verify_password

    statuses: list[SeedAccountStatus] = []
    for account in accounts:
        user = db.query(User).filter(User.username == account.username).first()
        exists = user is not None
        password_ok = False
        if exists and user.password_hash:
            try:
                password_ok = bool(verify_password(account.password, user.password_hash))
            except (ValueError, TypeError):
                password_ok = False
        statuses.append(
            SeedAccountStatus(
                username=account.username,
                expected_role=account.role,
                exists=exists,
                password_matches=password_ok,
                role_matches=exists and str(user.role) == account.role,
            )
        )
    aligned = bool(statuses) and all(
        s.exists and s.password_matches and s.role_matches for s in statuses
    )
    return SeedAuthCheck(accounts=tuple(statuses), aligned=aligned).sealed()


# ---------------------------------------------------------------------------
# T040 Design Engine walkthrough receipt
# ---------------------------------------------------------------------------


class DesignEngineFlags(BaseModel):
    """Flag snapshot for the walkthrough. Values only; no secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: str
    enable_patchbook_design_engine: bool
    enable_canon_export_fulfillment: bool
    enable_inline_export_fulfillment: bool
    enable_patchbook_publication_profile: bool
    stripe_test_mode: bool
    allow_production_payments: bool

    @classmethod
    def from_settings(cls, settings_obj: Any) -> "DesignEngineFlags":
        return cls(
            environment=str(getattr(settings_obj, "environment", "")),
            enable_patchbook_design_engine=bool(
                getattr(settings_obj, "enable_patchbook_design_engine", False)
            ),
            enable_canon_export_fulfillment=bool(
                getattr(settings_obj, "enable_canon_export_fulfillment", False)
            ),
            enable_inline_export_fulfillment=bool(
                getattr(settings_obj, "enable_inline_export_fulfillment", False)
            ),
            enable_patchbook_publication_profile=bool(
                getattr(settings_obj, "enable_patchbook_publication_profile", False)
            ),
            stripe_test_mode=bool(getattr(settings_obj, "stripe_test_mode", False)),
            allow_production_payments=bool(getattr(settings_obj, "allow_production_payments", True)),
        )


def flags_test_mode_failures(flags: DesignEngineFlags) -> tuple[str, ...]:
    """Design Engine flags on, payments in test mode, never production."""
    failed: list[str] = []
    if not flags.enable_patchbook_design_engine:
        failed.append("DESIGN_ENGINE_FLAG_OFF")
    if not flags.enable_canon_export_fulfillment:
        failed.append("EXPORT_FULFILLMENT_FLAG_OFF")
    if not flags.stripe_test_mode:
        failed.append("PAYMENTS_NOT_TEST_MODE")
    if flags.allow_production_payments:
        failed.append("PRODUCTION_PAYMENTS_ENABLED")
    if flags.environment.strip().lower() in {"production", "prod"}:
        failed.append("PRODUCTION_ENVIRONMENT")
    return tuple(failed)


class WalkthroughStart(_Sealed):
    schema_version: str = WALKTHROUGH_START_SCHEMA
    fe_cutover_sha256: str
    flags: DesignEngineFlags
    record_sha256: str = ""


def start_walkthrough(fe_cutover: FeCutoverEvidence, flags: DesignEngineFlags) -> WalkthroughStart:
    if not fe_cutover.intact():
        raise CutoverError("FE_CUTOVER_TAMPERED")
    fe_failed = fe_cutover_failures(fe_cutover)
    if fe_failed:
        raise CutoverError("FE_CUTOVER_INCOMPLETE", ",".join(fe_failed))
    failed = flags_test_mode_failures(flags)
    if failed:
        raise CutoverError("FLAGS_NOT_TEST_MODE", ",".join(failed))
    return WalkthroughStart(fe_cutover_sha256=fe_cutover.record_sha256, flags=flags).sealed()


class WalkthroughStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    http_status: int | None = None


REQUIRED_WALKTHROUGH_STEPS: tuple[str, ...] = (
    "health_ready",
    "login_user",
    "login_admin",
    "preview",
    "grant_credits",
    "export_debit",
    "fulfillment",
    "download_token",
    "download_pack",
)


class WalkthroughOutcome(BaseModel):
    """Result of the debit -> fulfillment -> download pack flow. Hashes only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: tuple[WalkthroughStep, ...]
    export_id: str | None = None
    export_status: str | None = None
    pack_manifest_hash: str | None = None
    composition_hash: str | None = None
    pack_zip_sha256: str | None = None

    @property
    def passed(self) -> bool:
        by_name = {step.name: step for step in self.steps}
        return (
            all(name in by_name and by_name[name].passed for name in REQUIRED_WALKTHROUGH_STEPS)
            and self.export_status == "succeeded"
            and bool(self.export_id)
            and _HEX64.match(self.pack_zip_sha256 or "") is not None
        )


class HealthSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    http_status: int
    status: str
    database: str

    @property
    def ok(self) -> bool:
        return self.http_status == 200 and self.status == "healthy" and self.database == "ok"


class WalkthroughReceipt(_Sealed):
    schema_version: str = WALKTHROUGH_RECEIPT_SCHEMA
    source_commit_sha: str
    walkthrough_start_sha256: str
    fe_cutover_sha256: str
    flags: DesignEngineFlags
    health: HealthSnapshot
    seed_auth_sha256: str
    seed_auth_aligned: bool
    seed_auth: SeedAuthCheck
    outcome: WalkthroughOutcome
    outcome_passed: bool
    production_payments_enabled: Literal[False] = False
    record_sha256: str = ""


def capture_walkthrough_receipt(
    *,
    start: WalkthroughStart | None,
    seed_auth: SeedAuthCheck | None,
    health: HealthSnapshot | None,
    outcome: WalkthroughOutcome | None,
    source_commit_sha: str,
) -> WalkthroughReceipt:
    """Seal the walkthrough receipt. Fails closed on seed auth, health, or outcome."""
    if start is None or not start.intact():
        raise CutoverError("WALKTHROUGH_NOT_STARTED")
    if seed_auth is None or not seed_auth.intact():
        raise CutoverError("SEED_AUTH_MISSING_OR_TAMPERED")
    if not seed_auth.aligned:
        raise CutoverError("SEED_AUTH_NOT_ALIGNED")
    if health is None or not health.ok:
        raise CutoverError("HEALTH_NOT_OK")
    if outcome is None or not outcome.passed:
        raise CutoverError("WALKTHROUGH_FAILED")
    if not is_pinned_sha(source_commit_sha):
        raise CutoverError("SOURCE_SHA_NOT_PINNED")
    failed = flags_test_mode_failures(start.flags)
    if failed:
        raise CutoverError("FLAGS_NOT_TEST_MODE", ",".join(failed))
    receipt = WalkthroughReceipt(
        source_commit_sha=source_commit_sha,
        walkthrough_start_sha256=start.record_sha256,
        fe_cutover_sha256=start.fe_cutover_sha256,
        flags=start.flags,
        health=health,
        seed_auth_sha256=seed_auth.record_sha256,
        seed_auth_aligned=True,
        seed_auth=seed_auth,
        outcome=outcome,
        outcome_passed=True,
    )
    return receipt.sealed()


# ---------------------------------------------------------------------------
# T050 readiness docs pinned to the walkthrough SHA
# ---------------------------------------------------------------------------


class PinnedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    content_sha256: str
    references_source_sha: bool


class ReadinessPin(_Sealed):
    schema_version: str = READINESS_PIN_SCHEMA
    walkthrough_receipt_sha256: str
    source_commit_sha: str
    documents: tuple[PinnedDocument, ...]
    unresolved_p0: tuple[str, ...]
    enablement_receipt: EvaluationEnablementReceipt
    pinned_by: str = Field(min_length=1)
    record_sha256: str = ""


REQUIRED_PIN_DOCUMENTS: tuple[str, ...] = (
    "docs/evidence/PRODUCTION_READINESS_MATRIX.md",
    "docs/evidence/DOMAIN_CUTOVER_CHECKLIST.md",
)


def pin_readiness_docs(
    *,
    receipt: WalkthroughReceipt | None,
    documents: Mapping[str, str],
    unresolved_p0: Iterable[str],
    enablement_receipt: EvaluationEnablementReceipt | None,
    pinned_by: str,
) -> ReadinessPin:
    """Bind the readiness matrix and cutover checklist to the walkthrough SHA.

    ``documents`` maps repo-relative path to file text. Each required document
    must reference the receipt's exact ``source_commit_sha``. ``unresolved_p0``
    lists open P0 integrity regressions; any entry fails closed. The Spec 007
    staging enablement receipt is the upstream dependency and must verify.
    """
    if receipt is None or not receipt.intact():
        raise CutoverError("WALKTHROUGH_RECEIPT_MISSING_OR_TAMPERED")
    if enablement_receipt is None or not verify_enablement_receipt(enablement_receipt):
        raise CutoverError("ENABLEMENT_RECEIPT_INVALID")
    missing = [path for path in REQUIRED_PIN_DOCUMENTS if path not in documents]
    if missing:
        raise CutoverError("PIN_DOCUMENT_MISSING", ",".join(missing))
    open_p0 = tuple(sorted({str(item) for item in unresolved_p0 if str(item).strip()}))
    if open_p0:
        raise CutoverError("UNRESOLVED_P0", ",".join(open_p0))
    pinned = tuple(
        PinnedDocument(
            path=path,
            content_sha256=hashlib.sha256(documents[path].encode("utf-8")).hexdigest(),
            references_source_sha=receipt.source_commit_sha in documents[path],
        )
        for path in sorted(documents)
    )
    unpinned = [doc.path for doc in pinned if doc.path in REQUIRED_PIN_DOCUMENTS and not doc.references_source_sha]
    if unpinned:
        raise CutoverError("DOCUMENT_NOT_PINNED_TO_SHA", ",".join(unpinned))
    if not pinned_by or not pinned_by.strip():
        raise CutoverError("OPERATOR_MISSING")
    record = ReadinessPin(
        walkthrough_receipt_sha256=receipt.record_sha256,
        source_commit_sha=receipt.source_commit_sha,
        documents=pinned,
        unresolved_p0=(),
        enablement_receipt=enablement_receipt,
        pinned_by=pinned_by,
    )
    return record.sealed()


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class CutoverState(str, Enum):
    INVENTORY_LEGACY = "INVENTORY_LEGACY"
    F5_ALIAS_LIVE = "F5_ALIAS_LIVE"
    FE_CUTOVER = "FE_CUTOVER"
    WALKTHROUGH_PENDING = "WALKTHROUGH_PENDING"
    RECEIPT_CAPTURED = "RECEIPT_CAPTURED"
    BETA_ELIGIBLE = "BETA_ELIGIBLE"


CUTOVER_ORDER: tuple[CutoverState, ...] = tuple(CutoverState)


class CutoverEventType(str, Enum):
    EXPOSE_CANON_ALIAS = "expose_canon_alias"
    SWITCH_FE_LIST = "switch_fe_list"
    RUN_WALKTHROUGH = "run_walkthrough"
    CAPTURE_RECEIPT = "capture_receipt"
    OPERATOR_PIN = "operator_pin"


S = CutoverState
E = CutoverEventType

TRANSITIONS: Mapping[tuple[CutoverState, CutoverEventType], CutoverState] = MappingProxyType(
    {
        (S.INVENTORY_LEGACY, E.EXPOSE_CANON_ALIAS): S.F5_ALIAS_LIVE,
        (S.F5_ALIAS_LIVE, E.SWITCH_FE_LIST): S.FE_CUTOVER,
        (S.FE_CUTOVER, E.RUN_WALKTHROUGH): S.WALKTHROUGH_PENDING,
        (S.WALKTHROUGH_PENDING, E.CAPTURE_RECEIPT): S.RECEIPT_CAPTURED,
        (S.RECEIPT_CAPTURED, E.OPERATOR_PIN): S.BETA_ELIGIBLE,
    }
)


@dataclass(frozen=True)
class CutoverEvent:
    """One event plus the artifact that satisfies its guard (others ignored)."""

    type: CutoverEventType
    alias: AliasParityEvidence | None = None
    fe_cutover: FeCutoverEvidence | None = None
    start: WalkthroughStart | None = None
    receipt: WalkthroughReceipt | None = None
    pin: ReadinessPin | None = None


@dataclass(frozen=True)
class CutoverTransition:
    from_state: CutoverState
    event: CutoverEventType
    to_state: CutoverState
    accepted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CutoverMachine:
    state: CutoverState = CutoverState.INVENTORY_LEGACY
    alias: AliasParityEvidence | None = None
    fe_cutover: FeCutoverEvidence | None = None
    start: WalkthroughStart | None = None
    receipt: WalkthroughReceipt | None = None
    pin: ReadinessPin | None = None
    history: tuple[CutoverTransition, ...] = field(default_factory=tuple)


def new_machine() -> CutoverMachine:
    return CutoverMachine()


def _guard_alias(m: CutoverMachine, ev: CutoverEvent) -> tuple[str, ...]:
    alias = ev.alias
    if alias is None:
        return ("ALIAS_EVIDENCE_MISSING",)
    failed: list[str] = []
    if not alias.intact():
        failed.append("ALIAS_EVIDENCE_TAMPERED")
    if alias.missing_alias_routes:
        failed.append("F2_F4_ALIASES_MISSING")
    if not alias.same_set or alias.legacy_ids_sha256 != alias.canon_ids_sha256:
        failed.append("ALIAS_SET_DIFFERS_FROM_LEGACY")
    if alias.new_write_surface:
        failed.append("NEW_WRITE_SURFACE")
    return tuple(failed)


def _guard_fe(m: CutoverMachine, ev: CutoverEvent) -> tuple[str, ...]:
    fe = ev.fe_cutover
    if m.alias is None:
        return ("ALIAS_NOT_LIVE",)
    if fe is None:
        return ("FE_CUTOVER_EVIDENCE_MISSING",)
    failed: list[str] = []
    if not fe.intact():
        failed.append("FE_CUTOVER_TAMPERED")
    if fe.alias_evidence_sha256 != m.alias.record_sha256:
        failed.append("FE_CUTOVER_NOT_LINKED_TO_ALIAS")
    failed.extend(fe_cutover_failures(fe))
    return tuple(failed)


def _guard_walkthrough(m: CutoverMachine, ev: CutoverEvent) -> tuple[str, ...]:
    start = ev.start
    if m.fe_cutover is None:
        return ("FE_NOT_CUT_OVER",)
    if start is None:
        return ("WALKTHROUGH_START_MISSING",)
    failed: list[str] = []
    if not start.intact():
        failed.append("WALKTHROUGH_START_TAMPERED")
    if start.fe_cutover_sha256 != m.fe_cutover.record_sha256:
        failed.append("WALKTHROUGH_NOT_LINKED_TO_FE_CUTOVER")
    failed.extend(flags_test_mode_failures(start.flags))
    return tuple(failed)


def _guard_capture(m: CutoverMachine, ev: CutoverEvent) -> tuple[str, ...]:
    receipt = ev.receipt
    if m.start is None or m.fe_cutover is None:
        return ("WALKTHROUGH_NOT_STARTED",)
    if receipt is None:
        return ("WALKTHROUGH_RECEIPT_MISSING",)
    failed: list[str] = []
    if not receipt.intact():
        failed.append("WALKTHROUGH_RECEIPT_TAMPERED")
    if receipt.walkthrough_start_sha256 != m.start.record_sha256:
        failed.append("RECEIPT_NOT_LINKED_TO_WALKTHROUGH")
    if receipt.fe_cutover_sha256 != m.fe_cutover.record_sha256:
        failed.append("RECEIPT_NOT_LINKED_TO_FE_CUTOVER")
    if receipt.flags != m.start.flags:
        failed.append("FLAGS_CHANGED_DURING_WALKTHROUGH")
    failed.extend(flags_test_mode_failures(receipt.flags))
    seed = receipt.seed_auth
    if not seed.intact() or receipt.seed_auth_sha256 != seed.record_sha256:
        failed.append("SEED_AUTH_TAMPERED")
    if not (receipt.seed_auth_aligned and seed.aligned) or not seed.accounts or not all(
        a.exists and a.password_matches and a.role_matches for a in seed.accounts
    ):
        failed.append("SEED_AUTH_NOT_ALIGNED")
    if not receipt.health.ok:
        failed.append("HEALTH_NOT_OK")
    if not (receipt.outcome_passed and receipt.outcome.passed):
        failed.append("WALKTHROUGH_FAILED")
    if not is_pinned_sha(receipt.source_commit_sha):
        failed.append("SOURCE_SHA_NOT_PINNED")
    return tuple(failed)


def _guard_pin(m: CutoverMachine, ev: CutoverEvent) -> tuple[str, ...]:
    pin = ev.pin
    if m.receipt is None:
        return ("WALKTHROUGH_RECEIPT_MISSING",)
    if pin is None:
        return ("READINESS_PIN_MISSING",)
    failed: list[str] = []
    if not m.receipt.intact():
        failed.append("WALKTHROUGH_RECEIPT_TAMPERED")
    if not pin.intact():
        failed.append("READINESS_PIN_TAMPERED")
    if pin.walkthrough_receipt_sha256 != m.receipt.record_sha256:
        failed.append("PIN_NOT_LINKED_TO_RECEIPT")
    if pin.source_commit_sha != m.receipt.source_commit_sha:
        failed.append("PIN_SOURCE_SHA_MISMATCH")
    paths = {doc.path for doc in pin.documents}
    if any(path not in paths for path in REQUIRED_PIN_DOCUMENTS):
        failed.append("PIN_DOCUMENT_MISSING")
    if any(not doc.references_source_sha for doc in pin.documents if doc.path in REQUIRED_PIN_DOCUMENTS):
        failed.append("DOCUMENT_NOT_PINNED_TO_SHA")
    if pin.unresolved_p0:
        failed.append("UNRESOLVED_P0")
    if not verify_enablement_receipt(pin.enablement_receipt):
        failed.append("ENABLEMENT_RECEIPT_INVALID")
    return tuple(failed)


_GUARDS = MappingProxyType(
    {
        E.EXPOSE_CANON_ALIAS: _guard_alias,
        E.SWITCH_FE_LIST: _guard_fe,
        E.RUN_WALKTHROUGH: _guard_walkthrough,
        E.CAPTURE_RECEIPT: _guard_capture,
        E.OPERATOR_PIN: _guard_pin,
    }
)

_ARTIFACT_FIELD = MappingProxyType(
    {
        E.EXPOSE_CANON_ALIAS: "alias",
        E.SWITCH_FE_LIST: "fe_cutover",
        E.RUN_WALKTHROUGH: "start",
        E.CAPTURE_RECEIPT: "receipt",
        E.OPERATOR_PIN: "pin",
    }
)


def transition(machine: CutoverMachine, event: CutoverEvent) -> CutoverMachine:
    """Apply one event. Rejections are recorded and leave state unchanged."""
    from dataclasses import replace

    if machine.state is S.BETA_ELIGIBLE:
        reasons: tuple[str, ...] = ("BETA_ELIGIBLE_IMMUTABLE",)
    else:
        target = TRANSITIONS.get((machine.state, event.type))
        if target is None:
            reasons = (f"INVALID_TRANSITION:{machine.state.value}:{event.type.value}",)
        else:
            reasons = _GUARDS[event.type](machine, event)
            if not reasons:
                name = _ARTIFACT_FIELD[event.type]
                return replace(
                    machine,
                    state=target,
                    history=machine.history
                    + (CutoverTransition(machine.state, event.type, target, True, ()),),
                    **{name: getattr(event, name)},
                )
    return replace(
        machine,
        history=machine.history
        + (CutoverTransition(machine.state, event.type, machine.state, False, reasons),),
    )


def replay(events: Iterable[CutoverEvent]) -> CutoverMachine:
    machine = new_machine()
    for event in events:
        machine = transition(machine, event)
    return machine


def beta_eligible(machine: CutoverMachine) -> bool:
    """True only at BETA_ELIGIBLE with an intact, linked receipt and pin and
    production payments disabled."""
    receipt = machine.receipt
    pin = machine.pin
    return (
        machine.state is S.BETA_ELIGIBLE
        and receipt is not None
        and pin is not None
        and receipt.intact()
        and pin.intact()
        and pin.walkthrough_receipt_sha256 == receipt.record_sha256
        and receipt.outcome_passed
        and not receipt.flags.allow_production_payments
    )
