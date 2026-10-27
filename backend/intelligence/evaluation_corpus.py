"""Evaluation corpus freeze (Spec 007, T010).

Promotes a governed, rights-cleared, reviewed pilot manifest into an immutable
CorpusFreeze record whose SHA-256 is recorded and re-verifiable.

Admission is delegated to the existing governed validator
(``scripts/validate_vision_pilot.py``, Spec 005 T061a/T060b). This module adds a
defense-in-depth cross-partition leakage check and refuses to freeze anything the
validator did not admit. Nothing here promotes a case, edits evidence, chooses
thresholds, or performs network, database, or provider calls. Image bytes are
never read: only retained image hashes are referenced.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from intelligence.contracts import stable_sha256

CORPUS_FREEZE_SCHEMA = "patchhive.eval-corpus-freeze.v1"
ADMITTED_STATUS = "ADMITTED_FOR_BASELINE"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")

Validator = Callable[[dict], dict]


class CorpusFreezeError(ValueError):
    """Raised when a manifest cannot be frozen. ``code`` is stable and secret-free."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class FrozenCorpusCase(BaseModel):
    """Minimal, hash-only projection of one admitted pilot case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    partition: str = Field(min_length=1)
    cohort: str = Field(min_length=1)
    expected_choice: str = Field(min_length=1)
    image_asset_hashes: tuple[str, ...] = Field(min_length=1)
    candidate_set_hash: str = Field(min_length=1)

    @field_validator("image_asset_hashes")
    @classmethod
    def _hashes_well_formed(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not _IMAGE_HASH.match(item):
                raise ValueError("image_asset_hashes must be sha256:<64 hex>")
        return value

    def image_sha256_hex(self) -> frozenset[str]:
        return frozenset(item.split(":", 1)[1] for item in self.image_asset_hashes)


class CorpusFreeze(BaseModel):
    """Immutable record of a frozen evaluation corpus.

    ``corpus_sha256`` is computed over the full validated manifest cases (sorted by
    case_id) and pilot version. ``record_sha256`` covers every other field of this
    record. Both are re-verified by :func:`verify_corpus_freeze`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = CORPUS_FREEZE_SCHEMA
    pilot_version: str = Field(min_length=1)
    corpus_sha256: str
    validator_manifest_sha256: str
    admission_status: str
    case_count: int = Field(ge=1)
    identity_count: int = Field(ge=1)
    partitions: dict[str, int]
    cohorts: dict[str, int]
    cases: tuple[FrozenCorpusCase, ...]
    record_sha256: str = ""

    def content_sha256(self) -> str:
        return stable_sha256(self.model_dump(mode="json", exclude={"record_sha256"}))

    def case_index(self) -> Mapping[str, FrozenCorpusCase]:
        return {case.case_id: case for case in self.cases}


def corpus_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Stable digest of a pilot manifest's cases and version.

    Independent of key order, whitespace, and case ordering. Status/notes fields
    are excluded so annotations cannot change the identity of the corpus.
    """
    cases = manifest.get("cases") or []
    rows = sorted((dict(case) for case in cases), key=lambda row: str(row.get("case_id")))
    return stable_sha256({"pilot_version": manifest.get("pilot_version"), "cases": rows})


def cross_partition_leakage(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Return stable error codes for any image hash or case_id seen in >1 partition."""
    errors: list[str] = []
    image_partition: dict[str, str] = {}
    case_partition: dict[str, str] = {}
    for case in manifest.get("cases") or []:
        cid = str(case.get("case_id"))
        partition = str(case.get("partition"))
        prior_case = case_partition.get(cid)
        if prior_case is not None and prior_case != partition:
            errors.append(f"{cid}:cross_partition_case_leakage")
        case_partition.setdefault(cid, partition)
        for image_hash in case.get("image_asset_hashes") or []:
            prior = image_partition.get(image_hash)
            if prior is not None and prior != partition:
                errors.append(f"{cid}:cross_partition_image_leakage:{image_hash}")
            image_partition.setdefault(image_hash, partition)
    return tuple(errors)


def _default_validator_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "validate_vision_pilot.py"


def load_pilot_validator(path: Path | None = None) -> Validator:
    """Load the governed pilot admission validator. Fails closed when absent."""
    script = path or _default_validator_path()
    if not script.is_file():
        raise CorpusFreezeError("CORPUS_VALIDATOR_UNAVAILABLE", "pilot validator not found")
    spec = importlib.util.spec_from_file_location("_patchhive_validate_vision_pilot", script)
    if spec is None or spec.loader is None:
        raise CorpusFreezeError("CORPUS_VALIDATOR_UNAVAILABLE", "pilot validator not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate = getattr(module, "validate", None)
    if not callable(validate):
        raise CorpusFreezeError("CORPUS_VALIDATOR_UNAVAILABLE", "validate() missing")
    return validate


def freeze_corpus(
    manifest: Mapping[str, Any] | None,
    *,
    validator: Validator | None = None,
) -> CorpusFreeze:
    """Freeze an admitted pilot manifest. Raises CorpusFreezeError on any failure."""
    if manifest is None or not isinstance(manifest, Mapping):
        raise CorpusFreezeError("CORPUS_MISSING")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CorpusFreezeError("CORPUS_EMPTY")
    pilot_version = manifest.get("pilot_version")
    if not isinstance(pilot_version, str) or not pilot_version.strip():
        raise CorpusFreezeError("CORPUS_VERSION_MISSING")

    leakage = cross_partition_leakage(manifest)
    if leakage:
        raise CorpusFreezeError("CROSS_PARTITION_LEAKAGE", ";".join(leakage))

    validate = validator or load_pilot_validator()
    report = validate(dict(manifest))
    errors = list(report.get("errors") or [])
    if any("cross_partition" in str(error) for error in errors):
        raise CorpusFreezeError("CROSS_PARTITION_LEAKAGE", ";".join(map(str, errors)))
    if errors or report.get("admission_status") != ADMITTED_STATUS:
        raise CorpusFreezeError(
            "ADMISSION_REJECTED",
            f"status={report.get('admission_status')} errors={len(errors)}",
        )

    try:
        frozen_cases = tuple(
            sorted(
                (
                    FrozenCorpusCase(
                        case_id=case["case_id"],
                        partition=case["partition"],
                        cohort=case["cohort"],
                        expected_choice=case["expected_choice"],
                        image_asset_hashes=tuple(case["image_asset_hashes"]),
                        candidate_set_hash=case["candidate_set_hash"],
                    )
                    for case in cases
                ),
                key=lambda row: row.case_id,
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusFreezeError("CORPUS_CASE_INVALID") from exc

    record = CorpusFreeze(
        pilot_version=pilot_version,
        corpus_sha256=corpus_manifest_sha256(manifest),
        validator_manifest_sha256=str(report.get("manifest_sha256", "")),
        admission_status=ADMITTED_STATUS,
        case_count=len(frozen_cases),
        identity_count=int(report.get("identity_count") or 0),
        partitions=dict(report.get("partitions") or {}),
        cohorts=dict(report.get("cohorts") or {}),
        cases=frozen_cases,
    )
    return record.model_copy(update={"record_sha256": record.content_sha256()})


def verify_corpus_freeze(
    record: CorpusFreeze | None,
    manifest: Mapping[str, Any] | None = None,
) -> bool:
    """True when the record is intact and (optionally) still matches the manifest."""
    if record is None or not isinstance(record, CorpusFreeze):
        return False
    if record.admission_status != ADMITTED_STATUS:
        return False
    if not _HEX64.match(record.corpus_sha256 or ""):
        return False
    if record.record_sha256 != record.content_sha256():
        return False
    case_ids = [case.case_id for case in record.cases]
    if len(case_ids) != len(set(case_ids)) or record.case_count != len(case_ids):
        return False
    if manifest is not None and corpus_manifest_sha256(manifest) != record.corpus_sha256:
        return False
    return True
