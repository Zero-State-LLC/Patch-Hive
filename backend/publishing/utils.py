"""Utilities for publishing layer."""

import re
import secrets

# 96 random bits (spec 002 T038), so a crawler can't guess an unlisted link. The column
# holds 160 characters, so a long title is cut to fit.
SLUG_TOKEN_BYTES = 12
SLUG_LENGTH = 160


def slugify_title(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return base or "publication"


def unique_slug(base: str) -> str:
    token = secrets.token_hex(SLUG_TOKEN_BYTES)
    return f"{base[: SLUG_LENGTH - len(token) - 1].rstrip('-') or 'publication'}-{token}"
