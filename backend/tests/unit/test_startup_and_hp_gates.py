"""Production refuses decision providers; HP overlays must cite a maker page."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import population as P  # noqa: E402
from core.startup_policy import validate_decision_startup_policy  # noqa: E402


def _settings(**overrides):
    base = {"environment": "production", "enable_decision_intelligence": False,
            "enable_clef_provider": False, "decision_provider": "disabled"}
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.parametrize(
    "overrides",
    [{"enable_decision_intelligence": True}, {"enable_clef_provider": True}, {"decision_provider": "jev"}],
)
def test_production_refuses_to_start_with_a_decision_provider(overrides) -> None:
    with pytest.raises(RuntimeError, match="not enabled in production"):
        validate_decision_startup_policy(_settings(**overrides))


def test_staging_and_a_clean_production_start() -> None:
    validate_decision_startup_policy(_settings())
    validate_decision_startup_policy(_settings(environment="staging", enable_clef_provider=True, decision_provider="clef"))


CATALOG = {"acme-vco": {"brand": "Acme", "name": "VCO", "hp": None, "category": "VCO"}}


def _plan(entry, **kwargs):
    catalog = {k: dict(v) for k, v in CATALOG.items()}
    plan = P.Plan()
    P._schedule_hp(plan, catalog, entry, **kwargs)
    return plan, catalog


def test_a_maker_cited_hp_fills() -> None:
    plan, catalog = _plan({"slug": "acme-vco", "brand": "Acme", "name": "VCO", "hp": 10,
                           "source_class": "maker", "source_url": "https://acme.example/vco"})
    assert catalog["acme-vco"]["hp"] == 10 and plan.updates == {"hp_overlay": 1}


@pytest.mark.parametrize(
    "extra",
    [{}, {"source_class": "maker_or_retail"}, {"source_class": "maker"}, {"source_class": "maker", "source_url": "http://x"}],
)
def test_an_unsourced_hp_is_refused(extra) -> None:
    plan, catalog = _plan({"slug": "acme-vco", "brand": "Acme", "name": "VCO", "hp": 10, **extra})
    assert catalog["acme-vco"]["hp"] is None
    assert [c["reason"] for c in plan.conflicts] == ["hp_overlay_unsourced"]


def test_only_the_named_legacy_overlay_is_grandfathered() -> None:
    plan, catalog = _plan({"slug": "acme-vco", "brand": "Acme", "name": "VCO", "hp": 10,
                           "source_class": "maker_or_retail"}, legacy_unsourced=True)
    assert catalog["acme-vco"]["hp"] == 10
    assert P.UNSOURCED_HP_OVERLAYS == frozenset({"module-catalog-hp-v1.json"})
