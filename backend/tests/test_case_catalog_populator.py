"""Tests for deterministic modular-case catalog ingestion."""

from __future__ import annotations

from sqlalchemy.orm import Session

from cases.models import CaseCatalog, CasePrice, CaseRevision, CaseSource
from cases.source_policy import CaseSourcePolicyPacket
from integrations.case_catalog_populator import import_records, validate_record


def _record() -> dict:
    return {
        "manufacturer": "Test Instruments",
        "model": "Travel 84",
        "format_family": "eurorack",
        "production_status": "available",
        "powered": True,
        "official_url": "https://example.com/travel-84",
        "revision": {
            "revision_key": "v1",
            "revision_label": "Version 1",
            "row_count": 1,
            "capacity_value": 84,
            "capacity_unit": "hp",
            "depth_max_mm": 55,
            "portable": True,
            "confidence": "verified",
        },
        "rows": [
            {
                "row_index": 0,
                "format_family": "eurorack",
                "capacity_value": 84,
                "capacity_unit": "hp",
                "depth_max_mm": 55,
            }
        ],
        "power_systems": [
            {
                "name": "primary",
                "supply_type": "external_brick",
                "connector_count": 16,
                "current_pos12_ma": 1500,
                "current_neg12_ma": 1000,
                "current_pos5_ma": 500,
            }
        ],
        "features": [
            {
                "feature_key": "removable_lid",
                "feature_value": "yes",
                "verified": True,
            }
        ],
        "sources": [
            {
                "source_type": "official_manual",
                "title": "Travel 84 Manual",
                "url": "https://example.com/travel-84-manual.pdf",
                "field_path": "revision.depth_max_mm",
                "published_value": "55 mm",
                "normalized_value": "55.0",
                "confidence": "verified",
                "policy": {
                    "access_basis": "official_publication",
                    "license_status": "public technical documentation",
                    "evidence_status": "MANUAL_CONFIRMED",
                    "review_state": "accepted",
                    "observed_at": "2026-07-21T12:00:00Z",
                    "retrieved_at": "2026-07-21T12:05:00Z",
                    "content_hash": "a" * 64,
                    "normalizer_version": "case-catalog-v1",
                    "notes": "Depth from official manual table",
                },
            }
        ],
        "prices": [
            {
                "source_name": "Test Dealer",
                "source_url": "https://example.com/store/travel-84",
                "amount": "499.00",
                "currency": "USD",
                "region": "US",
                "price_type": "street",
                "in_stock": True,
                "captured_at": "2026-07-21T12:10:00Z",
            }
        ],
    }


def test_validate_record_rejects_invalid_policy_enum() -> None:
    record = _record()
    record["sources"][0]["policy"]["access_basis"] = "scraped_without_basis"

    errors = validate_record(record, 0)

    assert any("policy.access_basis" in error for error in errors)


def test_import_is_idempotent_and_preserves_policy(db_session: Session) -> None:
    first = import_records(db_session, [_record()])
    second = import_records(db_session, [_record()])

    assert first["inserted"] == 1
    assert first["rejected"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 1
    assert second["rejected"] == 0
    assert db_session.query(CaseCatalog).count() == 1
    assert db_session.query(CaseRevision).count() == 1
    assert db_session.query(CaseSource).count() == 1
    assert db_session.query(CaseSourcePolicyPacket).count() == 1
    assert db_session.query(CasePrice).count() == 1

    packet = db_session.query(CaseSourcePolicyPacket).one()
    assert packet.access_basis == "official_publication"
    assert packet.evidence_status == "MANUAL_CONFIRMED"
    assert packet.review_state == "accepted"
    assert packet.content_hash == "a" * 64
    assert packet.notes == "Depth from official manual table"


def test_dry_run_rolls_back_all_catalog_writes(db_session: Session) -> None:
    receipt = import_records(db_session, [_record()], dry_run=True)

    assert receipt["inserted"] == 1
    assert receipt["rejected"] == 0
    assert db_session.query(CaseCatalog).count() == 0
    assert db_session.query(CaseSourcePolicyPacket).count() == 0
    assert db_session.query(CasePrice).count() == 0


def test_reload_never_overwrites_non_null_fields(db_session: Session) -> None:
    import_records(db_session, [_record()])
    db_session.commit()
    revision = db_session.query(CaseRevision).one()
    case = db_session.query(CaseCatalog).one()
    revision.depth_max_mm = 77
    case.official_url = "https://example.com/hand-edited"
    db_session.commit()

    changed = _record()
    changed["revision"]["depth_max_mm"] = 99
    changed["official_url"] = "https://example.com/from-seed"
    receipt = import_records(db_session, [changed])

    assert receipt["updated"] == 0
    assert receipt["unchanged"] == 1
    db_session.refresh(revision)
    db_session.refresh(case)
    assert revision.depth_max_mm == 77
    assert case.official_url == "https://example.com/hand-edited"


def test_reload_fills_null_fields_and_counts_real_change(db_session: Session) -> None:
    import_records(db_session, [_record()])
    db_session.commit()
    revision = db_session.query(CaseRevision).one()
    revision.depth_max_mm = None
    db_session.commit()

    receipt = import_records(db_session, [_record()])

    assert receipt["updated"] == 1
    assert receipt["unchanged"] == 0
    db_session.refresh(revision)
    assert revision.depth_max_mm == 55
