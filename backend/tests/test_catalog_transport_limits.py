"""Spec 003 FR-011: direct fetches check the content type and size before reading."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import catalog_scrape as cs  # noqa: E402


class _Resp:
    def __init__(self, body: bytes, headers: dict[str, str], status: int = 200):
        self._body = body
        self.headers = headers
        self.status = status

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, resp: _Resp):
    class _Opener:
        def open(self, request, timeout=None):
            return resp

    monkeypatch.setattr(cs, "public_http_url", lambda url: True)
    monkeypatch.setattr(cs.urllib.request, "build_opener", lambda *a: _Opener())
    request = cs.HttpRequest("GET", "https://maker.example/p", {}, None, 5.0)
    return cs.default_transport(request)


def test_html_is_read_and_headers_kept(monkeypatch):
    resp = _serve(monkeypatch, _Resp(b"<html>ok</html>", {"Content-Type": "text/html; charset=utf-8"}))
    assert resp.status == 200 and resp.body == b"<html>ok</html>"
    assert resp.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize("media", ["application/pdf", "image/png", "application/octet-stream"])
def test_other_content_types_are_refused_unread(monkeypatch, media):
    resp = _serve(monkeypatch, _Resp(b"%PDF-1.7", {"Content-Type": media}))
    assert resp.status == 0 and resp.body == b""
    assert resp.headers[cs.REFUSED_HEADER] == "MIME_NOT_ALLOWED"


def test_oversized_bodies_are_refused(monkeypatch):
    big = b"x" * (cs.MAX_BODY_BYTES + 1)
    resp = _serve(monkeypatch, _Resp(big, {"Content-Type": "text/html"}))
    assert resp.status == 0 and resp.headers[cs.REFUSED_HEADER] == "BODY_TOO_LARGE"
    declared = _serve(monkeypatch, _Resp(b"", {"Content-Type": "text/html", "Content-Length": str(10**9)}))
    assert declared.headers[cs.REFUSED_HEADER] == "BODY_TOO_LARGE"


def test_a_missing_content_type_is_read_but_still_bounded(monkeypatch):
    resp = _serve(monkeypatch, _Resp(b"User-agent: *", {}))
    assert resp.status == 200 and resp.body == b"User-agent: *"
