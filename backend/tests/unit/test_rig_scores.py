"""Spec 001 OQ-11 option 2: routing_flex_score and performance_density_index."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from canon.contracts import NOT_COMPUTABLE, ModulePort, RigMetricsPacket
from canon.models import RigRevisionRecord
from canon.rig_metrics import build_rig_metrics_packet
from canon.rig_scores import METRICS_GENERATOR_VERSION, compute_rig_scores
from modules.models import Module

OTHER_FOUR = (
    "modulation_budget",
    "clock_coherence_score",
    "chaos_headroom",
    "learning_gradient_index",
)


def test_computable_rig_uses_the_decided_formulas() -> None:
    flex, density, notes = compute_rig_scores([4, 6, 2], [10, 8, 6])
    assert flex == round(1 - math.exp(-(12 / 3) / 8), 4) == 0.3935
    assert density == round(12 / 24, 4) == 0.5
    text = " ".join(notes)
    assert "round(1 - exp(-(total_ports / module_count) / 8), 4)" in text
    assert "round(total_ports / total_hp, 4)" in text
    assert "3/3" in text


@pytest.mark.parametrize("empty", [None, 0])
def test_one_empty_ports_module_makes_both_scores_not_computable(empty) -> None:
    flex, density, notes = compute_rig_scores([4, empty, 2], [10, 8, 6])
    assert flex == NOT_COMPUTABLE and density == NOT_COMPUTABLE
    assert "2/3" in " ".join(notes)


@pytest.mark.parametrize("bad_hp", [None, 0])
def test_null_or_zero_hp_blocks_only_the_density_index(bad_hp) -> None:
    flex, density, _ = compute_rig_scores([4, 6], [10, bad_hp])
    assert flex == round(1 - math.exp(-5 / 8), 4)
    assert density == NOT_COMPUTABLE


def test_empty_rig_is_not_computable_not_zero() -> None:
    flex, density, _ = compute_rig_scores([], [])
    assert flex == NOT_COMPUTABLE and density == NOT_COMPUTABLE


def _module(db: Session, name: str, hp: int, module_type: str, ports: list) -> Module:
    row = Module(
        brand="T", name=name, module_type=module_type, hp=hp, io_ports=ports, source="test"
    )
    db.add(row)
    db.commit()
    return row


def _packet(db: Session, modules: list[Module]) -> RigMetricsPacket:
    revision = RigRevisionRecord(
        id="rev-x",
        rig_id=1,
        schema_version="t",
        canonical_rig={"modules": [{"module_id": m.id} for m in modules]},
        canonical_hash="h",
    )
    return build_rig_metrics_packet(db, revision, source_run_id="run-x")


PORTS = [{"name": "In", "type": "cv_in"}, {"name": "Out", "type": "audio_out"}]


def test_packet_computed_with_version_and_notes(db_session: Session) -> None:
    a = _module(db_session, "A", 10, "VCO", PORTS)
    b = _module(db_session, "B", 6, "VCF", PORTS * 2)
    packet = _packet(db_session, [a, b])
    assert packet.generator_version == METRICS_GENERATOR_VERSION == "canon-metrics.1.2.0"
    assert packet.routing_flex_score == round(1 - math.exp(-3 / 8), 4)
    assert packet.performance_density_index == round(6 / 16, 4)
    for name in OTHER_FOUR:
        assert getattr(packet, name) == NOT_COMPUTABLE
    assert any("2/2" in n for n in packet.confidence_notes)
    assert any("round(1 - exp(" in n for n in packet.confidence_notes)


def test_packet_with_empty_ports_module_is_not_computable(db_session: Session) -> None:
    a = _module(db_session, "A", 10, "VCO", PORTS)
    b = _module(db_session, "B", 6, "VCF", [])
    packet = _packet(db_session, [a, b])
    assert packet.routing_flex_score == NOT_COMPUTABLE
    assert packet.performance_density_index == NOT_COMPUTABLE
    assert any("1/2" in n for n in packet.confidence_notes)


def test_blank_panel_is_not_exempt(db_session: Session) -> None:
    """The catalog has no reliable blank-panel marker, so a UTIL module with no ports
    still blocks both scores."""
    a = _module(db_session, "A", 10, "VCO", PORTS)
    blank = _module(db_session, "Blank 4hp", 4, "UTIL", [])
    assert _packet(db_session, [a, blank]).routing_flex_score == NOT_COMPUTABLE


def test_map_metrics_follows_the_same_rule_and_suggest_layouts_guards() -> None:
    from canon.runes import build_canonical_rig, map_metrics, suggest_layouts
    from canon.contracts import EpistemicStatus, ModuleRevision, RigModule, RigSpec

    stamped = datetime(2025, 12, 21, tzinfo=timezone.utc)

    def rev(rid: str, ports: tuple, hp: int | None = 8) -> ModuleRevision:
        return ModuleRevision(
            module_revision_id=rid, module_gallery_id=f"g-{rid}", manufacturer="M", name=rid,
            hp=hp, ports=ports, status=EpistemicStatus.confirmed, created_at=stamped,
        )

    port = ModulePort(port_id="p", label="P", direction="input", signal_type="cv")

    def run(revisions: dict):
        spec = RigSpec(
            rig_id="r",
            name="r",
            modules=tuple(
                RigModule(instance_id=k, module_revision_id=k, position=i)
                for i, k in enumerate(revisions)
            ),
        )
        rig = build_canonical_rig(spec, revisions)
        metrics = map_metrics(rig, revisions, run_id="x", seed=1, created_at=stamped)
        return rig, metrics

    rig, metrics = run({"a": rev("a", (port, port)), "b": rev("b", (port,))})
    assert metrics.routing_flex_score == round(1 - math.exp(-1.5 / 8), 4)
    assert metrics.performance_density_index == round(3 / 16, 4)
    assert metrics.generator_version == METRICS_GENERATOR_VERSION
    layouts = suggest_layouts(rig, metrics, run_id="x", seed=1, created_at=stamped)
    assert layouts[0].score == metrics.routing_flex_score

    rig, metrics = run({"a": rev("a", (port,)), "b": rev("b", ())})
    assert metrics.routing_flex_score == NOT_COMPUTABLE
    with pytest.raises(ValueError, match="NOT_COMPUTABLE"):
        suggest_layouts(rig, metrics, run_id="x", seed=1, created_at=stamped)
