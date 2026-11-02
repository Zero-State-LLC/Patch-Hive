#!/usr/bin/env python3
"""Find openly licensed candidate photos for the spec 007 evaluation corpus.

Owner direction (2026-11-02, in chat): use context.dev to find photos of modular
synths, capped at 300 searches. Approval entry ``corpus-photos-2026-11`` in
``data/synth-catalog/receipts/fetch-approvals.json`` carries that cap (FR-003).

    starter  catalog seeds/overlays + slugs  -> identities.json
    search   identities.json                 -> OUT_DIR/{candidates.jsonl, modules.jsonl,
                                                summary.json, receipts.jsonl, images/}

``search`` runs one search per identity through ``CatalogScraper`` (free DuckDuckGo
first, then context.dev under the approval gate and the spend ledger). It is
context.dev-only: FIRECRAWL_API_KEY is removed from the process environment for
the run, and any Firecrawl call aborts it. Results are kept only for Wikimedia
Commons ``/wiki/File:`` pages and Flickr photo pages. Each page is fetched with a
free GET (robots.txt respected; Commons disallows /w/api.php, so the File page
HTML is parsed instead). Only CC0, public domain, CC BY and CC BY-SA (any version)
are accepted; everything else is recorded with an exclusion reason. Accepted
originals are downloaded with plain GETs (robots respected, 2 s per host, 20 MB
cap, JPEG/PNG/WebP only) into OUT_DIR/images/, which must be outside any git
checkout. Image bytes never enter the repo.

Rows are candidates for ``scripts/build_vision_promotion_queue.py``. Ground truth
stays UNVERIFIED: the searched identity is a proposal, and an operator must still
verify identity and review each case before admission.

Usage (repo root, backend venv):
  python scripts/vision/find_corpus_photos.py starter \\
      --slugs mutable-instruments-plaits,make-noise-maths --out ~/patchhive-corpus/identities.json
  python scripts/vision/find_corpus_photos.py search \\
      --identities ~/patchhive-corpus/identities.json --out-dir ~/patchhive-corpus/photos
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "data" / "synth-catalog"
if str(CATALOG) not in sys.path:
    sys.path.insert(0, str(CATALOG))

from catalog_scrape import (  # noqa: E402
    USER_AGENT,
    CatalogScraper,
    HttpRequest,
    HttpResponse,
    check_paid_approval,
    denied_host,
    parse_robots,
    public_http_url,
)

APPROVAL_ID = "corpus-photos-2026-11"
# The approval entry lists this scope as its only "brand", so it admits this tool's searches
# and nothing else: catalog crawls pass real brand names (or none) and are refused by it.
APPROVAL_SCOPE = (APPROVAL_ID,)
MAX_SEARCHES = 300
RESULTS_PER_SEARCH = 10
HOST_INTERVAL_S = 2.0
MAX_IMAGE_BYTES = 20 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
IMAGE_HOSTS = ("upload.wikimedia.org", "live.staticflickr.com")
COMMONS_HOSTS = {"commons.wikimedia.org", "commons.m.wikimedia.org"}
FLICKR_HOSTS = {"flickr.com", "www.flickr.com", "m.flickr.com"}
FLICKR_PHOTO = re.compile(r"^/photos/([^/]+)/(\d+)(?:/|$)")
# Flickr size suffixes, smallest to largest; "" is the 500 px default.
FLICKR_SIZES = (
    "s",
    "q",
    "t",
    "m",
    "n",
    "w",
    "",
    "z",
    "c",
    "b",
    "h",
    "k",
    "3k",
    "4k",
    "5k",
    "6k",
    "o",
)
FLICKR_IMAGE = re.compile(
    r"(?:https?:)?//live\.staticflickr\.com/\d+/(\d+)_[0-9a-f]+(?:_([a-z0-9]+))?\.(?:jpe?g|png)",
    re.I,
)
RACK_WORDS = re.compile(r"\b(rack|racks|case|skiff|setup|rig)\b", re.I)
PANEL_WORDS = re.compile(r"\b(front panel|faceplate|panel)\b", re.I)


# --------------------------------------------------------------------------- rights


@dataclass(frozen=True)
class License:
    accepted: bool
    name: str | None
    url: str | None
    reason: str | None  # exclusion reason when not accepted


def _version(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return f"-{match.group(1)}" if match else ""


def classify_license(text: str | None, url: str | None = None) -> License:
    """Accept CC0, public domain, CC BY and CC BY-SA (any version); exclude the rest with a reason."""
    raw_text = (text or "").strip()
    raw_url = (url or "").strip()
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url
    probe_url = raw_url.lower()
    probe = raw_text.lower()
    if not probe and not probe_url:
        return License(False, None, None, "no_license_found")

    cc = re.search(
        r"creativecommons\.org/(licenses|publicdomain)/([a-z0-9\-]+)/?([0-9.]*)", probe_url
    )
    if cc:
        kind, code, version = cc.groups()
        suffix = f"-{version}" if version else ""
        if kind == "publicdomain":
            if code == "zero":
                return License(True, f"CC0{suffix or '-1.0'}", raw_url, None)
            if code == "mark":
                return License(True, "Public domain (PDM)", raw_url, None)
            return License(False, raw_text or code, raw_url, "license_not_allowed")
        parts = code.split("-")
        if "nc" in parts:
            return License(False, f"CC-{code.upper()}{suffix}", raw_url, "non_commercial")
        if "nd" in parts:
            return License(False, f"CC-{code.upper()}{suffix}", raw_url, "no_derivatives")
        if parts == ["by"]:
            return License(True, f"CC-BY{suffix}", raw_url, None)
        if parts == ["by", "sa"]:
            return License(True, f"CC-BY-SA{suffix}", raw_url, None)
        return License(False, f"CC-{code.upper()}{suffix}", raw_url, "license_not_allowed")

    link = raw_url or None
    if "all rights reserved" in probe:
        return License(False, "All rights reserved", link, "all_rights_reserved")
    if re.search(r"\bnc\b|non-?commercial", probe):
        return License(False, raw_text, link, "non_commercial")
    if re.search(r"\bnd\b|no ?derivative", probe):
        return License(False, raw_text, link, "no_derivatives")
    if re.search(r"\bcc0\b|cc zero|public domain dedication", probe):
        return License(True, "CC0-1.0" if "1.0" in probe else "CC0", link, None)
    if re.search(r"^public domain\b|^pd\b|^pd-", probe):
        return License(True, "Public domain", link, None)
    if re.search(r"\bcc[ -]by[ -]sa\b|attribution[ -]share ?alike", probe):
        return License(True, "CC-BY-SA" + _version(probe), link, None)
    if re.search(r"\bcc[ -]by\b|^attribution\b", probe):
        return License(True, "CC-BY" + _version(probe), link, None)
    if "no known copyright restrictions" in probe:
        return License(False, raw_text, link, "rights_ambiguous")
    return License(
        False, raw_text or None, link, "license_not_allowed" if raw_text else "no_license_found"
    )


class _Collector(HTMLParser):
    """Collects text of elements by class/id, and selected attributes, from one page."""

    VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "wbr",
    }

    def __init__(self, classes: set[str], ids: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.classes, self.ids = classes, ids
        self.found: dict[str, list[str]] = {}
        self.anchors: list[dict[str, str]] = []
        self.metas: dict[str, str] = {}
        self.title = ""
        self._open: list[tuple[str, int, list[str]]] = []  # (key, depth at open, text parts)
        self._depth = 0
        self._in_title = False
        self._after_author: str | None = None  # "pending" once the author label cell closed

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag == "a":
            self.anchors.append(data)
        if tag == "meta":
            key = data.get("property") or data.get("name")
            if key and "content" in data:
                self.metas.setdefault(key.lower(), data["content"])
        if tag == "title":
            self._in_title = True
        if tag in self.VOID:
            return
        self._depth += 1
        keys = [c for c in data.get("class", "").split() if c in self.classes]
        if data.get("id") in self.ids:
            keys.append(data["id"])
        if tag == "td" and self._after_author == "pending":
            keys.append("author_cell")
            self._after_author = None
        for key in keys:
            self._open.append((key, self._depth, []))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self.VOID:
            return
        still: list[tuple[str, int, list[str]]] = []
        for key, depth, parts in self._open:
            if depth == self._depth:
                self.found.setdefault(key, []).append(re.sub(r"\s+", " ", "".join(parts)).strip())
                if key == "fileinfotpl_aut":
                    self._after_author = "pending"
            else:
                still.append((key, depth, parts))
        self._open = still
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        for _, _, parts in self._open:
            parts.append(data)


@dataclass
class PhotoPage:
    host: str  # "commons" | "flickr"
    url: str
    title: str
    description: str
    license: License
    author: str | None
    image_url: str | None


def normalize_photo_url(url: str) -> tuple[str, str] | None:
    """(kind, canonical page URL) for a Commons File page or a Flickr photo page, else None."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return None
    if host in COMMONS_HOSTS and parsed.path.startswith("/wiki/File:"):
        name = parsed.path[len("/wiki/") :]
        return "commons", f"https://commons.wikimedia.org/wiki/{name}"
    if host in FLICKR_HOSTS:
        match = FLICKR_PHOTO.match(parsed.path)
        if match:
            return "flickr", f"https://www.flickr.com/photos/{match.group(1)}/{match.group(2)}/"
    return None


def parse_commons_page(url: str, html: str) -> PhotoPage:
    page = _Collector(
        {
            "licensetpl_short",
            "licensetpl_link",
            "licensetpl_attr",
            "licensetpl_aut",
            "fullMedia",
            "description",
        },
        {"fileinfotpl_aut"},
    )
    page.feed(html or "")
    shorts = page.found.get("licensetpl_short", [])
    links = page.found.get("licensetpl_link", [])
    chosen = License(False, None, None, "no_license_found")
    # A file may carry several license templates (dual licensing); the first accepted one is used.
    for index, short in enumerate(shorts):
        link = links[index] if index < len(links) else None
        verdict = classify_license(short, link)
        if verdict.accepted:
            chosen = verdict
            break
        if chosen.reason == "no_license_found":
            chosen = verdict
    author = _first(page.found.get("licensetpl_attr")) or _first(page.found.get("licensetpl_aut"))
    author = author or _first(page.found.get("author_cell"))
    image_url = None
    for anchor in page.anchors:
        href = anchor.get("href", "")
        full = urljoin("https://commons.wikimedia.org/", href)
        host = (urlparse(full).hostname or "").lower()
        if (
            host == "upload.wikimedia.org"
            and "/thumb/" not in full
            and "internal" in anchor.get("class", "")
        ):
            image_url = full
            break
    if image_url is None:
        for anchor in page.anchors:
            full = urljoin("https://commons.wikimedia.org/", anchor.get("href", ""))
            if (urlparse(full).hostname or "") == "upload.wikimedia.org" and "/thumb/" not in full:
                image_url = full
                break
    title = re.sub(r"\s*-\s*Wikimedia Commons\s*$", "", page.title.strip())
    description = _first(page.found.get("description")) or ""
    return PhotoPage("commons", url, title, description[:500], chosen, author, image_url)


def parse_flickr_page(url: str, html: str) -> PhotoPage:
    page = _Collector({"owner-name", "photo-license-url"}, set())
    page.feed(html or "")
    # Only the photo's own license link counts. Flickr pages also embed the full list of
    # licenses in their page model, so a bare creativecommons.org match is not evidence.
    license_url = None
    for anchor in page.anchors:
        rels = anchor.get("rel", "").lower().split()
        if anchor.get("href") and (
            "license" in rels or "photo-license-url" in anchor.get("class", "").split()
        ):
            license_url = anchor["href"]
            break
    text = None
    if license_url is None and re.search(r"all rights reserved", html or "", re.I):
        text = "All rights reserved"
    verdict = classify_license(text, license_url)
    author = _first(page.found.get("owner-name")) or page.metas.get("flickr_photos:by") or None
    match = FLICKR_PHOTO.match(urlparse(url).path)
    photo_id = match.group(2) if match else None
    title = page.metas.get("og:title") or re.sub(r"\s*\|\s*Flickr\s*$", "", page.title.strip())
    description = page.metas.get("og:description") or page.metas.get("description") or ""
    return PhotoPage(
        "flickr", url, title, description[:500], verdict, author, _largest_flickr(html, photo_id)
    )


def _largest_flickr(html: str, photo_id: str | None) -> str | None:
    best: tuple[int, str] | None = None
    for match in FLICKR_IMAGE.finditer((html or "").replace("\\/", "/")):
        if photo_id and match.group(1) != photo_id:
            continue
        size = (match.group(2) or "").lower()
        rank = FLICKR_SIZES.index(size) if size in FLICKR_SIZES else -1
        found = match.group(0)
        found = "https:" + found if found.startswith("//") else found
        if best is None or rank > best[0]:
            best = (rank, found)
    return best[1] if best else None


def _first(values: list[str] | None) -> str | None:
    for value in values or []:
        if value:
            return value[:300]
    return None


# --------------------------------------------------------------------------- downloads


def image_transport(request: HttpRequest) -> HttpResponse:
    """Plain GET for robots.txt and image originals: public hosts only, bounded read."""
    if not public_http_url(request.url):
        return HttpResponse(0, b"", {})

    class _Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
            if not public_http_url(newurl) or denied_host(newurl):
                raise urllib.error.HTTPError(req.full_url, code, "refusing redirect", headers, fp)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_Redirect)
    raw = urllib.request.Request(request.url, headers=request.headers, method="GET")
    try:
        with opener.open(raw, timeout=request.timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            declared = headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
                return HttpResponse(0, b"", {**headers, "x-refused": "too_large"})
            body = resp.read(MAX_IMAGE_BYTES + 1)
            return HttpResponse(getattr(resp, "status", 200), body, headers)
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, b"", {})
    except Exception:
        return HttpResponse(0, b"", {})


MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


class ImageDownloader:
    """robots.txt-respecting, host-spaced, size- and type-bounded image GETs into one directory."""

    def __init__(
        self,
        images_dir: Path,
        *,
        transport: Callable[[HttpRequest], HttpResponse] = image_transport,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        interval_s: float = HOST_INTERVAL_S,
        max_bytes: int = MAX_IMAGE_BYTES,
    ) -> None:
        self.images_dir = images_dir
        self.transport = transport
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.interval_s = interval_s
        self.max_bytes = max_bytes
        self._robots: dict[str, str | None] = {}
        self._next_ok: dict[str, float] = {}
        self._done: dict[str, dict] = {}

    def download(self, url: str) -> dict:
        """{"ok", "reason", "sha256", "path", "bytes", "content_type"} for one image URL."""
        if url in self._done:
            return self._done[url]
        result = self._download(url)
        self._done[url] = result
        return result

    def _download(self, url: str) -> dict:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or host not in IMAGE_HOSTS
            or denied_host(url)
            or not public_http_url(url)
        ):
            return {"ok": False, "reason": "image_host_not_allowed"}
        origin = f"https://{host}"
        if origin not in self._robots:
            response = self._get(origin + "/robots.txt", "text/plain,*/*;q=0.5")
            if response.status == 404:
                self._robots[origin] = ""
            elif response.status == 200:
                self._robots[origin] = response.body.decode("utf-8", errors="replace")
            else:
                self._robots[origin] = None
        rules = self._robots[origin]
        if rules is None:
            return {"ok": False, "reason": "robots_unavailable"}
        if not parse_robots(rules, USER_AGENT, parsed.path or "/"):
            return {"ok": False, "reason": "robots_disallowed"}
        response = self._get(url, "image/jpeg,image/png,image/webp")
        if response.status != 200:
            return {"ok": False, "reason": f"http_{response.status}"}
        media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media not in IMAGE_TYPES:
            return {"ok": False, "reason": "mime_not_allowed"}
        body = response.body
        if not body or len(body) > self.max_bytes:
            return {"ok": False, "reason": "too_large" if body else "empty_body"}
        if not body.startswith(MAGIC[media]):
            return {"ok": False, "reason": "content_not_image"}
        digest = hashlib.sha256(body).hexdigest()
        name = f"{digest}.{IMAGE_TYPES[media]}"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        target = self.images_dir / name
        if not target.exists():
            target.write_bytes(body)
        return {
            "ok": True,
            "reason": None,
            "sha256": digest,
            "path": f"images/{name}",
            "bytes": len(body),
            "content_type": media,
        }

    def _get(self, url: str, accept: str) -> HttpResponse:
        host = (urlparse(url).hostname or "").lower()
        now = self.monotonic()
        slot = max(now, self._next_ok.get(host, 0.0))
        self._next_ok[host] = slot + self.interval_s
        if slot > now:
            self.sleeper(slot - now)
        try:
            return self.transport(
                HttpRequest("GET", url, {"User-Agent": USER_AGENT, "Accept": accept}, None, 60)
            )
        except Exception:
            return HttpResponse(0, b"", {})


# --------------------------------------------------------------------------- guards


class Refused(Exception):
    """A precondition failed; nothing was searched or fetched."""


def check_out_dir(out_dir: Path) -> Path:
    """Resolve OUT_DIR and refuse a path inside this repo or any other git checkout."""
    resolved = out_dir.expanduser().resolve()
    root = REPO_ROOT.resolve()
    if resolved == root or root in resolved.parents:
        raise Refused(
            f"--out-dir {resolved} is inside the repository {root}; image bytes never go in the repo"
        )
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise Refused(f"--out-dir {resolved} is inside the git checkout {parent}")
    return resolved


def remaining_allowance(
    approvals_path: Path, ledger_path: Path, approval_id: str = APPROVAL_ID
) -> int:
    """Paid calls left under the named approval entry (fetches and credits since its baseline)."""
    try:
        doc = json.loads(approvals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refused(f"cannot read {approvals_path.name}: {exc}") from exc
    entry = next(
        (e for e in doc.get("entries") or [] if isinstance(e, dict) and e.get("id") == approval_id),
        None,
    )
    if entry is None:
        raise Refused(f"no approval entry {approval_id!r} in {approvals_path.name}")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    fetches = int(ledger.get("paid_fetches") or 0) - int(entry.get("ledger_baseline_fetches") or 0)
    credits = sum(float(v or 0) for v in (ledger.get("credits_by_backend") or {}).values())
    credits -= float(entry.get("ledger_baseline_credits") or 0)
    left = min(int(entry["cap_fetches"]) - fetches, int(float(entry["cap_credits"]) - credits))
    return max(0, left)


# --------------------------------------------------------------------------- search run


def load_identities(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise Refused("--identities must be a JSON list of {brand, name, slug, manufacturer_url}")
    out = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or not row.get("brand")
            or not row.get("name")
            or not row.get("slug")
        ):
            raise Refused(f"identity row needs brand, name and slug: {row!r}")
        out.append(
            {
                "brand": str(row["brand"]),
                "name": str(row["name"]),
                "slug": str(row["slug"]),
                "manufacturer_url": row.get("manufacturer_url") or None,
            }
        )
    return out


def search_query(identity: dict) -> str:
    return f'"{identity["brand"]} {identity["name"]}" eurorack (site:commons.wikimedia.org OR site:flickr.com)'


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def identity_match(identity: dict, page: PhotoPage) -> str | None:
    """Which page field names the searched module ("title" / "description"), else None."""
    wanted = _tokens(identity["name"])
    if not wanted:
        return None
    for field_name, text in (("title", unquote(page.title)), ("description", page.description)):
        have = set(_tokens(text))
        if all(token in have for token in wanted):
            return field_name
    return None


def proposed_cohort(page: PhotoPage) -> str | None:
    text = f"{unquote(page.title)} {page.description}"
    if RACK_WORDS.search(text):
        return "installed_rack"
    if PANEL_WORDS.search(text):
        return "clear_front_panel"
    return None


@dataclass
class Counts:
    searched: int = 0
    paid_searches: int = 0
    results: int = 0
    allowed_host_results: int = 0
    pages_fetched: int = 0
    page_fetch_failed: int = 0
    license_accepted: int = 0
    license_excluded: dict[str, int] = field(default_factory=dict)
    downloaded: int = 0
    download_failed: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "searched": self.searched,
            "paid_searches": self.paid_searches,
            "results": self.results,
            "allowed_host_results": self.allowed_host_results,
            "pages_fetched": self.pages_fetched,
            "page_fetch_failed": self.page_fetch_failed,
            "license_accepted": self.license_accepted,
            "license_excluded": dict(sorted(self.license_excluded.items())),
            "downloaded": self.downloaded,
            "download_failed": dict(sorted(self.download_failed.items())),
        }


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def _discovery_id(slug: str, page_url: str) -> str:
    return "photo-" + hashlib.sha256(f"{slug}\n{page_url}".encode()).hexdigest()[:20]


def _utc(wall: Callable[[], float]) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(wall()))


def rights_verdict(page: PhotoPage) -> tuple[bool, str | None]:
    """(accepted, exclusion reason). BY and BY-SA oblige attribution, so they need a recorded author."""
    lic = page.license
    if lic.accepted and (lic.name or "").startswith("CC-BY") and not page.author:
        return False, "attribution_missing"
    return lic.accepted, lic.reason


def build_row(identity: dict, page: PhotoPage, download: dict | None, retrieved_at: str) -> dict:
    lic = page.license
    rights_ok, reason = rights_verdict(page)
    if rights_ok:
        rights_status = "RIGHTS_CONFIRMED"
    elif reason in {
        "non_commercial",
        "no_derivatives",
        "all_rights_reserved",
        "license_not_allowed",
    }:
        rights_status = "RIGHTS_RESTRICTED"
    elif reason == "rights_ambiguous":
        rights_status = "RIGHTS_AMBIGUOUS"
    else:
        rights_status = "RIGHTS_UNKNOWN"
    downloaded = bool(download and download.get("ok"))
    match = identity_match(identity, page)
    sources = [
        {
            "kind": "photo_page_text",
            "url": page.url,
            "matched_field": match,
            "title": page.title[:300],
            "description": page.description,
        }
    ]
    if identity.get("manufacturer_url"):
        sources.append({"kind": "manufacturer_page", "url": identity["manufacturer_url"]})
    return {
        # Only retained, rights-confirmed bytes are an image_asset the promotion queue will import.
        "kind": "image_asset" if (rights_ok and downloaded) else "image_reference",
        "discovery_id": _discovery_id(identity["slug"], page.url),
        "source_url": page.url,
        "source_host": "commons.wikimedia.org" if page.host == "commons" else "flickr.com",
        "asset_url": page.image_url,
        "retrieved_at": retrieved_at,
        "linked_record_ids": [identity["slug"]],
        "manufacturer": identity["brand"],
        "model": identity["name"],
        "revision": None,
        "proposed_expected_choice": identity["slug"],
        "identity_sources": sources,
        "rights_status": rights_status,
        "rights_basis": (
            f"{lic.name} ({lic.url or 'license named on source page'}); author: {page.author}; source: {page.url}"
            if rights_ok
            else None
        ),
        "license": lic.name,
        "license_url": lic.url,
        "author": page.author,
        "exclusion_reason": None if rights_ok else reason,
        "image_sha256": f"sha256:{download['sha256']}" if downloaded and download else None,
        "image_path": download.get("path") if downloaded and download else None,
        "image_bytes": download.get("bytes") if downloaded and download else None,
        "content_type": download.get("content_type") if downloaded and download else None,
        "download_status": (
            "downloaded"
            if downloaded
            else (f"failed:{download['reason']}" if download else "not_attempted")
        ),
        "ground_truth_status": "UNVERIFIED",
        "annotation_status": "DISCOVERED",
        "reviewer": None,
        "proposed_cohort": proposed_cohort(page),
        "cohort": None,
        "partition": None,
        "used_for_tuning": None,
    }


def module_row(identity: dict) -> dict:
    """A modules.jsonl row for build_vision_promotion_queue.py (proposed identity, not ground truth)."""
    return {
        "record_id": identity["slug"],
        "manufacturer": identity["brand"],
        "model": identity["name"],
        "expected_choice": identity["slug"],
        "manufacturer_url": identity.get("manufacturer_url"),
        "ground_truth_status": "UNVERIFIED",
    }


def _no_firecrawl(receipt: dict) -> None:
    # A "skipped_no_key" receipt names the Firecrawl endpoint without calling it; only a real call aborts.
    if receipt.get("method") == "firecrawl":
        raise RuntimeError("Firecrawl was called; this run is context.dev-only")


def run_search(
    identities: list[dict],
    out_dir: Path,
    *,
    max_searches: int = MAX_SEARCHES,
    search_scraper_factory: Callable[..., CatalogScraper] | None = None,
    page_scraper_factory: Callable[..., CatalogScraper] | None = None,
    downloader: ImageDownloader | None = None,
    wall_clock: Callable[[], float] = time.time,
    log: Callable[[str], None] = lambda line: print(line, file=sys.stderr),
) -> dict:
    """Search, filter, check rights, download. Returns the counts summary; raises Refused up front."""
    out_dir = check_out_dir(out_dir)
    if max_searches < 1 or max_searches > MAX_SEARCHES:
        raise Refused(f"--max-searches must be 1..{MAX_SEARCHES}")
    brands = APPROVAL_SCOPE
    search_factory = search_scraper_factory or CatalogScraper.for_repo
    page_factory = page_scraper_factory or CatalogScraper.for_repo

    # Context.dev only (owner, 2026-11-02): no Firecrawl key in this process for the whole run.
    saved_firecrawl = os.environ.pop("FIRECRAWL_API_KEY", None)
    try:
        probe = search_factory(max_paid_fetches=0, brands=brands)
        if probe.approvals_path is None:
            raise Refused("search scraper has no approvals file; the FR-003 gate must apply")
        ok, why = check_paid_approval(
            probe.approvals_path, probe.ledger_path, brands, now=probe.wall_clock()
        )
        if not ok:
            raise Refused(f"paid search refused by the approval gate: {why}")
        left = remaining_allowance(probe.approvals_path, probe.ledger_path)
        if left < 1:
            raise Refused(f"approval {APPROVAL_ID} has no searches left")
        budget = min(max_searches, left)
        if budget < max_searches:
            log(f"--max-searches {max_searches} capped at the approval's remaining {left}")
        if not os.environ.get("CONTEXT_DEV_API_KEY", "").strip():
            log("CONTEXT_DEV_API_KEY is not set: searches are free DuckDuckGo only")

        searcher = search_factory(
            max_paid_fetches=budget,
            brands=brands,
            on_receipt=_no_firecrawl,
            min_interval_s=HOST_INTERVAL_S,
        )
        # Photo pages are free GETs only: no paid fallback, robots respected, 2 s per host.
        pages = page_factory(
            max_paid_fetches=0, on_receipt=_no_firecrawl, min_interval_s=HOST_INTERVAL_S
        )
        fetcher = downloader or ImageDownloader(out_dir / "images")
        counts = Counts()
        rows: list[dict] = []
        parsed_pages: dict[str, PhotoPage | None] = {}
        for identity in identities[:budget]:
            result = searcher.search(search_query(identity), limit=RESULTS_PER_SEARCH)
            counts.searched += 1
            counts.paid_searches += sum(
                1 for r in result.receipts if r.get("method") == "context_dev"
            )
            counts.results += len(result.urls)
            seen: set[str] = set()
            for raw_url in result.urls:
                normalized = normalize_photo_url(raw_url)
                if normalized is None or normalized[1] in seen:
                    continue
                kind, page_url = normalized
                seen.add(page_url)
                counts.allowed_host_results += 1
                if page_url not in parsed_pages:
                    fetched = pages.fetch(page_url)
                    if fetched.ok and fetched.text:
                        counts.pages_fetched += 1
                        parser = parse_commons_page if kind == "commons" else parse_flickr_page
                        parsed_pages[page_url] = parser(page_url, fetched.text)
                    else:
                        counts.page_fetch_failed += 1
                        parsed_pages[page_url] = None
                page = parsed_pages[page_url]
                if page is None:
                    continue
                download = None
                accepted, _ = rights_verdict(page)
                if accepted:
                    counts.license_accepted += 1
                    if page.image_url:
                        download = fetcher.download(page.image_url)
                    else:
                        download = {"ok": False, "reason": "no_image_url"}
                    if download.get("ok"):
                        counts.downloaded += 1
                    else:
                        _bump(counts.download_failed, download["reason"])
                row = build_row(identity, page, download, _utc(wall_clock))
                if not accepted:
                    _bump(counts.license_excluded, row["exclusion_reason"] or "unknown")
                rows.append(row)
    finally:
        if saved_firecrawl is not None:
            os.environ["FIRECRAWL_API_KEY"] = saved_firecrawl

    out_dir.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda row: row["discovery_id"])
    _write_jsonl(out_dir / "candidates.jsonl", rows)
    _write_jsonl(out_dir / "modules.jsonl", [module_row(i) for i in identities[:budget]])
    receipts = [
        {
            k: r.get(k)
            for k in ("url", "method", "status", "sha256", "timestamp", "credits", "note")
            if k in r
        }
        for r in searcher.receipts + pages.receipts
    ]
    _write_jsonl(out_dir / "receipts.jsonl", receipts)
    summary = {
        "approval_id": APPROVAL_ID,
        "max_searches": budget,
        "counts": counts.as_dict(),
        "ground_truth": "UNVERIFIED (operator must verify identity and review before admission)",
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


# --------------------------------------------------------------------------- starter


def _slug(brand: str, name: str) -> str:
    # Same rule as population.create_slug (kept local: population imports SQLAlchemy).
    return re.sub(r"[^a-z0-9]+", "-", f"{brand}-{name}".lower()).strip("-")


def catalog_identities(catalog: Path = CATALOG) -> dict[str, dict]:
    """slug -> {brand, name, slug, manufacturer_url} from the committed seeds and addition overlays."""
    rows: list[dict] = []
    for seed in sorted(catalog.glob("seed-phase*-v*.json")):
        doc = json.loads(seed.read_text(encoding="utf-8"))
        rows += doc.get("catalog_modules") or []
        rows += doc.get("full_spec_modules") or []
    for overlay in sorted((catalog / "overlays").glob("catalog-additions-v*.json")):
        rows += json.loads(overlay.read_text(encoding="utf-8")).get("rows") or []
    review = catalog / "overlays" / "maker-review-v1.json"
    if review.exists():
        rows += json.loads(review.read_text(encoding="utf-8")).get("catalog_rows") or []
    retired: set[str] = set()
    for retirement in sorted((catalog / "overlays").glob("catalog-retirements-v*.json")):
        retired |= {
            r.get("slug")
            for r in json.loads(retirement.read_text(encoding="utf-8")).get("rows") or []
        }
    found: dict[str, dict] = {}
    for row in rows:
        brand, name = row.get("brand"), row.get("name")
        if not brand or not name:
            continue
        slug = _slug(brand, name)
        if slug in retired:
            continue
        entry = found.setdefault(
            slug, {"brand": brand, "name": name, "slug": slug, "manufacturer_url": None}
        )
        url = row.get("manufacturer_url")
        if url and not entry["manufacturer_url"] and not denied_host(url):
            entry["manufacturer_url"] = url
    return found


def write_starter(
    slugs: list[str], out: Path, catalog: Path = CATALOG
) -> tuple[list[dict], list[str]]:
    known = catalog_identities(catalog)
    picked = [known[s] for s in slugs if s in known]
    missing = [s for s in slugs if s not in known]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(picked, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return picked, missing


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    starter = sub.add_parser("starter", help="write an identities file from the committed catalog")
    starter.add_argument("--slugs", default="", help="comma-separated catalog slugs")
    starter.add_argument("--slugs-file", type=Path, help="one slug per line")
    starter.add_argument("--out", required=True, type=Path)
    search = sub.add_parser("search", help="search, check licenses, download into --out-dir")
    search.add_argument("--identities", required=True, type=Path)
    search.add_argument("--out-dir", required=True, type=Path)
    search.add_argument("--max-searches", type=int, default=MAX_SEARCHES)
    args = parser.parse_args(argv)

    try:
        if args.command == "starter":
            slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
            if args.slugs_file:
                slugs += [s.strip() for s in args.slugs_file.read_text().splitlines() if s.strip()]
            if not slugs:
                raise Refused("give --slugs or --slugs-file")
            picked, missing = write_starter(slugs, args.out)
            print(json.dumps({"written": len(picked), "missing": missing, "out": str(args.out)}))
            return 1 if missing else 0
        summary = run_search(
            load_identities(args.identities), args.out_dir, max_searches=args.max_searches
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
