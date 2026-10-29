"""Canon pipeline: metrics + layouts + sealed compilation."""

from __future__ import annotations

from tests.canon_demo_pipeline import run_canon_pipeline


def test_pipeline_bundle() -> None:
    bundle = run_canon_pipeline(rig_id="rig.demo.v1", seed=101)
    assert bundle.rig_id == "rig.demo.v1"
    assert bundle.compilation.patch_graph.source_rig_revision_id == bundle.rig.rig_revision_id
    assert len(bundle.layouts) == 3
    assert bundle.metrics.module_count == 2
    assert bundle.compilation.validation_report.valid is True
    assert bundle.compilation.patch_plan.steps
