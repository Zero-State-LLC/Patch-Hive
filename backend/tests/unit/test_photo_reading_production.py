"""Spec 009 T040: production's answer is closed. Turning photo reading on there is an operator
action (T080), never a code default or a config line slipped into a deploy."""

from __future__ import annotations

from tests.edge_config import edge_source, wrangler


def _block(source: str, name: str) -> str:
    return source.split(f"const {name} = [", 1)[1].split("] as const;", 1)[0]


def test_production_sets_no_photo_reading_and_the_edge_forwards_none_there() -> None:
    production = wrangler()["vars"]
    assert not any(name.startswith("PHOTO_READING_") for name in production)
    # Only FLAG_VARS and STAGING_SECRETS stay out of production (src/index.ts); a photo-reading
    # name anywhere else in the edge would reach the production container.
    source = edge_source()
    assert (
        'if (env.ENVIRONMENT !== "production") names.push(...FLAG_VARS, ...STAGING_SECRETS);'
        in source
    )
    for staging_only in ("FLAG_VARS", "STAGING_SECRETS"):
        source = source.replace(_block(source, staging_only), "")
    assert "PHOTO_READING" not in source
