"""Tests for the acquisition-to-review-queue promotion workbench."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "build_vision_promotion_queue.py"
SPEC = spec_from_file_location("build_vision_promotion_queue", SCRIPT)
assert SPEC and SPEC.loader
module = module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_only_rights_confirmed_assets_enter_queue_and_unknowns_stay_unknown():
    discovery = [
        {
            "kind": "image_asset",
            "discovery_id": "d1",
            "linked_record_ids": ["m1"],
            "rights_status": "RIGHTS_CONFIRMED",
            "evidence_sha256": "a" * 64,
            "source_url": "https://example.invalid/a",
            "stated_copyright_or_license": "CC-BY-SA-3.0",
        },
        {
            "kind": "image_asset",
            "discovery_id": "d2",
            "linked_record_ids": ["m2"],
            "rights_status": "RIGHTS_RESTRICTED",
            "evidence_sha256": "b" * 64,
            "source_url": "https://example.invalid/b",
        },
        {
            "kind": "source_page",
            "discovery_id": "d3",
            "linked_record_ids": ["m1"],
            "rights_status": "RIGHTS_CONFIRMED",
            "evidence_sha256": "c" * 64,
            "source_url": "https://example.invalid/page",
        },
        {
            "discovery_id": "d4",
            "linked_record_ids": ["m1"],
            "rights_status": "RIGHTS_CONFIRMED",
            "evidence_sha256": "d" * 64,
            "source_url": "https://example.invalid/missing-kind",
        },
    ]
    modules = [{"record_id": "m1", "manufacturer": "Maker", "model": "Module"}]
    result = module.build_queue(discovery, modules)
    assert result["rights_cleared"] == 1
    assert result["admitted"] == 0
    item = result["items"][0]
    assert item["discovery_id"] == "d1"
    assert item["asset_hash"] == "sha256:" + "a" * 64
    assert item["identity_ref"] == "m1"
    assert item["identity_refs"] == ["m1"]
    assert item["proposed_identity"] == "Module"
    assert item["license"] == "CC-BY-SA-3.0"
    assert item["ground_truth_status"] == "UNVERIFIED"
    assert item["annotation_status"] == "DISCOVERED"
    assert item["reviewer"] is None
    assert item["used_for_tuning"] is None
    assert result["thresholds"] == "NOT_COMPUTABLE"


def test_multiple_identity_links_are_preserved_without_guessing_scalar_identity():
    discovery = [{
        "kind": "image_asset",
        "discovery_id": "d1",
        "linked_record_ids": ["m2", "m1"],
        "rights_status": "RIGHTS_CONFIRMED",
        "evidence_sha256": "a" * 64,
        "source_url": "https://example.invalid/a",
    }]
    modules = [
        {"record_id": "m1", "model": "One"},
        {"record_id": "m2", "model": "Two"},
    ]
    item = module.build_queue(discovery, modules)["items"][0]
    assert item["discovery_id"] == "d1"
    assert item["identity_refs"] == ["m1", "m2"]
    assert item["identity_ref"] is None
    assert item["proposed_identity"] is None


def test_queue_ids_do_not_collide_for_distinct_discovery_records():
    base = {
        "kind": "image_asset",
        "linked_record_ids": [],
        "rights_status": "RIGHTS_CONFIRMED",
        "source_url": "https://example.invalid/shared",
    }
    result = module.build_queue(
        [{**base, "discovery_id": "d1"}, {**base, "discovery_id": "d2"}],
        [],
    )
    assert len(result["items"]) == 2
    assert len({item["queue_id"] for item in result["items"]}) == 2
    assert {item["discovery_id"] for item in result["items"]} == {"d1", "d2"}


def test_queue_is_deterministic():
    discovery = [{
        "kind": "image_asset",
        "discovery_id": "d1",
        "linked_record_ids": ["m1"],
        "rights_status": "RIGHTS_CONFIRMED",
        "evidence_sha256": "a" * 64,
        "source_url": "https://example.invalid/a",
    }]
    modules = [{"record_id": "m1", "model": "Module"}]
    assert module.build_queue(discovery, modules) == module.build_queue(discovery, modules)
