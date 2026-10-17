#!/usr/bin/env python3
"""Build a deterministic review queue from retained PatchHive acquisition JSONL.

This tool never marks ground truth verified, annotations reviewed, or a case
admitted. It preserves unknowns for an operator to resolve.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _normalized_hash(row: dict) -> str | None:
    value = (
        row.get("evidence_sha256")
        or row.get("sha256")
        or row.get("image_sha256")
        or row.get("content_sha256")
    )
    if not value:
        return None
    value = str(value)
    return value if value.startswith("sha256:") else "sha256:" + value


def _linked_identity_refs(row: dict) -> list[str]:
    refs = row.get("linked_record_ids")
    if isinstance(refs, list):
        return sorted({str(ref) for ref in refs if ref})
    legacy = row.get("record_id") or row.get("module_id") or row.get("candidate_id")
    return [str(legacy)] if legacy else []


def build_queue(discovery: list[dict], modules: list[dict]) -> dict:
    module_by_id = {
        str(row.get("record_id") or row.get("module_id") or row.get("candidate_id")): row
        for row in modules
        if row.get("record_id") or row.get("module_id") or row.get("candidate_id")
    }
    items = []
    for row in discovery:
        # Promotion is asset-level and fail-closed: only explicit image evidence enters.
        if row.get("kind") != "image_asset":
            continue
        rights = row.get("rights_status") or row.get("rights_and_consent", {}).get("rights_status")
        if rights != "RIGHTS_CONFIRMED":
            continue

        asset_hash = _normalized_hash(row)
        identity_refs = _linked_identity_refs(row)
        identity_ref = identity_refs[0] if len(identity_refs) == 1 else None
        module = module_by_id.get(identity_ref, {}) if identity_ref else {}
        proposed_identity = (
            module.get("canonical_identity")
            or module.get("expected_choice")
            or module.get("model")
            or row.get("model")
        )
        source_url = row.get("source_url") or row.get("url") or ""
        item = {
            "queue_id": _sha({
                "asset_hash": asset_hash,
                "source_url": source_url,
                "identity_refs": identity_refs,
                "discovery_id": row.get("discovery_id"),
            }),
            "discovery_id": row.get("discovery_id"),
            "asset_hash": asset_hash,
            "source_url": source_url,
            "license": (
                row.get("stated_copyright_or_license")
                or row.get("license")
                or row.get("rights_license")
            ),
            "identity_ref": identity_ref,
            "identity_refs": identity_refs,
            "proposed_identity": proposed_identity,
            "manufacturer": module.get("manufacturer") or row.get("manufacturer"),
            "revision": module.get("revision") or row.get("revision"),
            "promotion_state": "NEEDS_OPERATOR_REVIEW",
            "ground_truth_status": "UNVERIFIED",
            "annotation_status": "DISCOVERED",
            "reviewer": None,
            "cohort": None,
            "partition": "development",
            "used_for_tuning": None,
            "candidate_set_hash": None,
            "expected_choice": None,
            "unresolved": [
                "ground_truth",
                "reviewer",
                "cohort",
                "contamination",
                "candidate_set",
            ],
        }
        items.append(item)
    items.sort(key=lambda item: item["queue_id"])
    return {
        "schema_version": "patchhive.pilot-promotion-queue.v1",
        "rights_cleared": len(items),
        "admitted": 0,
        "thresholds": "NOT_COMPUTABLE",
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", required=True, type=Path)
    parser.add_argument("--modules", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_queue(_read_jsonl(args.discovery), _read_jsonl(args.modules))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "rights_cleared": result["rights_cleared"],
        "admitted": 0,
        "thresholds": "NOT_COMPUTABLE",
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
