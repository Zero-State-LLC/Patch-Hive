"""Both Workers send the security headers the gap analysis found missing (2026-10-29)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_api_worker_secures_every_response() -> None:
    worker = (ROOT / "edge" / "api" / "src" / "index.ts").read_text(encoding="utf-8")
    for header in ('"Strict-Transport-Security": "max-age=31536000; includeSubDomains"',
                   '"X-Content-Type-Options": "nosniff"', '"X-Frame-Options": "DENY"'):
        assert header in worker
    assert "return withSecurityHeaders(await env.API.getByName(\"primary\").fetch(request));" in worker


def test_the_frontend_worker_sends_hsts() -> None:
    headers = (ROOT / "frontend" / "worker" / "headers.ts").read_text(encoding="utf-8")
    assert '"Strict-Transport-Security": "max-age=31536000; includeSubDomains"' in headers
