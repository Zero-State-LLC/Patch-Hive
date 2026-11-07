"""Copy compliance tests for dashboard and referral text."""

from pathlib import Path
import re

from tests.monorepo_paths import frontend_src


def test_dashboard_copy_compliance():
    """Ensure required copy is present and forbidden terms absent."""
    account_path = frontend_src() / "pages" / "Account.tsx"
    content = account_path.read_text(encoding="utf-8")

    required_lines = [
        "PatchHive is free to explore. You only pay when you export something you want to keep.",
        "You’ll receive free credits if your friend makes their first purchase.",
    ]
    for line in required_lines:
        assert line in content

    forbidden_terms = ["upgrade", "premium", "pro", "subscribe", "commission", "affiliate"]
    # The commerce parts of the Account page live in their own files; the same words stay out.
    commerce = [frontend_src() / "components" / "AccountCommerce.tsx", frontend_src() / "lib" / "commerce.ts"]
    lowered = "\n".join([content, *(path.read_text(encoding="utf-8") for path in commerce)]).lower()
    for term in forbidden_terms:
        assert re.search(rf"\b{re.escape(term)}\b", lowered) is None
