"""Offline tests for scripts/vision/find_corpus_photos.py (fake transports only, no network)."""

from __future__ import annotations

import json
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


photos = _load("find_corpus_photos", ROOT / "scripts" / "vision" / "find_corpus_photos.py")
queue = _load("build_vision_promotion_queue", ROOT / "scripts" / "build_vision_promotion_queue.py")
HttpRequest, HttpResponse, CatalogScraper = (
    photos.HttpRequest,
    photos.HttpResponse,
    photos.CatalogScraper,
)

JPEG = b"\xff\xd8\xff\xe0" + b"fake-jpeg-body" * 10
COMMONS_OK = "https://commons.wikimedia.org/wiki/File:Mutable_Instruments_Plaits.jpg"
COMMONS_GFDL = "https://commons.wikimedia.org/wiki/File:Plaits_gfdl.jpg"
FLICKR_OK = "https://www.flickr.com/photos/someone/123456/"
FLICKR_NC = "https://www.flickr.com/photos/other/777/"
COMMONS_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Mutable_Instruments_Plaits.jpg"
FLICKR_IMAGE_K = "https://live.staticflickr.com/65535/123456_abcdef_k.jpg"


def commons_html(
    short: str, link: str | None, attr: str | None = "Jane Doe", extra: str = ""
) -> str:
    link_span = f'<span class="licensetpl_link" style="display:none;">{link}</span>' if link else ""
    attr_span = f'<span class="licensetpl_attr" style="display:none;">{attr}</span>' if attr else ""
    return f"""<html><head><title>File:Mutable Instruments Plaits.jpg - Wikimedia Commons</title></head>
<body>
<div class="fullMedia"><p><bdi><a href="//upload.wikimedia.org/wikipedia/commons/thumb/a/ab/x.jpg/800px-x.jpg">
thumb</a><a href="https://upload.wikimedia.org/wikipedia/commons/a/ab/Mutable_Instruments_Plaits.jpg"
class="internal" title="Mutable_Instruments_Plaits.jpg">Original file</a></bdi></p></div>
<table><tr><td class="description">Mutable Instruments Plaits module in a eurorack case</td></tr>
<tr><td id="fileinfotpl_aut" class="fileinfo-paramfield">Author</td><td><a href="/wiki/User:Jane">Jane</a></td></tr>
</table>
{extra}
<table class="licensetpl"><tr><td><span class="licensetpl_short">{short}</span>{link_span}{attr_span}</td></tr></table>
</body></html>"""


def flickr_html(license_href: str | None, owner: str = "Some One") -> str:
    lic = (
        f'<a href="{license_href}" rel="license cc:license" class="photo-license-url">Some rights</a>'
        if license_href
        else ""
    )
    return f"""<html><head><title>Plaits in my rack | Flickr</title>
<meta property="og:title" content="Make Noise Maths in rack">
<meta property="og:image" content="https://live.staticflickr.com/65535/123456_abcdef_b.jpg">
</head><body><a class="owner-name" href="/photos/someone/">{owner}</a>{lic}
<script>modelExport = {{"sizes":{{"k":{{"url":"\\/\\/live.staticflickr.com\\/65535\\/123456_abcdef_k.jpg"}},
"c":{{"url":"\\/\\/live.staticflickr.com\\/65535\\/123456_abcdef_c.jpg"}},
"other":"//live.staticflickr.com/65535/999_ffff_o.jpg"}}}};
var licenses = ["https://creativecommons.org/licenses/by/2.0/"];</script></body></html>"""


# --------------------------------------------------------------------------- license parsing


@pytest.mark.parametrize(
    ("text", "url", "accepted", "name", "reason"),
    [
        (
            "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0",
            True,
            "CC-BY-SA-4.0",
            None,
        ),
        ("CC BY 2.0", None, True, "CC-BY-2.0", None),
        ("CC0", "http://creativecommons.org/publicdomain/zero/1.0/deed.en", True, "CC0-1.0", None),
        ("Public domain", None, True, "Public domain", None),
        (
            None,
            "https://creativecommons.org/publicdomain/mark/1.0/",
            True,
            "Public domain (PDM)",
            None,
        ),
        (
            None,
            "https://creativecommons.org/licenses/by-nc-sa/2.0/",
            False,
            "CC-BY-NC-SA-2.0",
            "non_commercial",
        ),
        (
            None,
            "https://creativecommons.org/licenses/by-nd/2.0/",
            False,
            "CC-BY-ND-2.0",
            "no_derivatives",
        ),
        ("CC BY-NC 3.0", None, False, "CC BY-NC 3.0", "non_commercial"),
        ("GFDL", "http://www.gnu.org/copyleft/fdl.html", False, "GFDL", "license_not_allowed"),
        ("All rights reserved", None, False, "All rights reserved", "all_rights_reserved"),
        (None, None, False, None, "no_license_found"),
    ],
)
def test_classify_license(text, url, accepted, name, reason):
    verdict = photos.classify_license(text, url)
    assert (verdict.accepted, verdict.name, verdict.reason) == (accepted, name, reason)


def test_commons_page_accepted_license_author_and_original():
    page = photos.parse_commons_page(
        COMMONS_OK, commons_html("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0")
    )
    assert page.license.accepted and page.license.name == "CC-BY-SA-4.0"
    assert page.license.url == "https://creativecommons.org/licenses/by-sa/4.0"
    assert page.author == "Jane Doe"
    assert page.image_url == COMMONS_IMAGE
    assert page.title == "File:Mutable Instruments Plaits.jpg"
    assert "eurorack case" in page.description


def test_commons_dual_license_uses_the_accepted_one_and_author_cell_fallback():
    extra = '<table><tr><td><span class="licensetpl_short">GFDL</span></td></tr></table>'
    html = commons_html(
        "CC BY 3.0", "https://creativecommons.org/licenses/by/3.0", attr=None, extra=extra
    )
    page = photos.parse_commons_page(COMMONS_OK, html)
    assert page.license.name == "CC-BY-3.0"
    assert page.author == "Jane"


@pytest.mark.parametrize(
    ("short", "link", "reason"),
    [
        ("GFDL", "http://www.gnu.org/copyleft/fdl.html", "license_not_allowed"),
        ("CC BY-NC-SA 2.0", "https://creativecommons.org/licenses/by-nc-sa/2.0", "non_commercial"),
    ],
)
def test_commons_page_excluded(short, link, reason):
    page = photos.parse_commons_page(COMMONS_OK, commons_html(short, link))
    assert not page.license.accepted and page.license.reason == reason


def test_commons_page_without_license_markup_is_unknown():
    page = photos.parse_commons_page(COMMONS_OK, "<html><title>File:x.jpg</title></html>")
    assert page.license.reason == "no_license_found"


def test_flickr_page_accepted_largest_size_and_owner():
    page = photos.parse_flickr_page(
        FLICKR_OK, flickr_html("https://creativecommons.org/licenses/by/2.0/")
    )
    assert page.license.accepted and page.license.name == "CC-BY-2.0"
    assert page.author == "Some One"
    assert page.image_url == FLICKR_IMAGE_K  # k beats b and c; the other photo's _o is ignored
    assert page.title == "Make Noise Maths in rack"


def test_flickr_page_excluded_cases():
    nc = photos.parse_flickr_page(
        FLICKR_NC, flickr_html("https://creativecommons.org/licenses/by-nc/2.0/")
    )
    assert nc.license.reason == "non_commercial"
    # The embedded license list is not the photo's license: no rel=license link means not accepted.
    arr = photos.parse_flickr_page(
        FLICKR_OK, flickr_html(None).replace("</body>", "All rights reserved</body>")
    )
    assert not arr.license.accepted and arr.license.reason == "all_rights_reserved"
    bare = photos.parse_flickr_page(FLICKR_OK, flickr_html(None))
    assert not bare.license.accepted and bare.license.reason == "no_license_found"


def test_cc_by_without_author_is_not_rights_confirmed():
    page = photos.parse_commons_page(
        COMMONS_OK,
        commons_html("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0", attr=None).replace(
            "fileinfotpl_aut", "fileinfotpl_other"
        ),
    )
    row = photos.build_row({"brand": "B", "name": "N", "slug": "b-n"}, page, None, "t")
    assert (
        row["rights_status"] == "RIGHTS_UNKNOWN"
        and row["exclusion_reason"] == "attribution_missing"
    )


# --------------------------------------------------------------------------- host filtering


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (COMMONS_OK + "?uselang=de#x", ("commons", COMMONS_OK)),
        (
            "https://commons.m.wikimedia.org/wiki/File:A.jpg",
            ("commons", "https://commons.wikimedia.org/wiki/File:A.jpg"),
        ),
        ("https://flickr.com/photos/someone/123456/in/photostream/", ("flickr", FLICKR_OK)),
        ("https://commons.wikimedia.org/wiki/Category:Eurorack", None),
        ("https://commons.wikimedia.org/w/api.php?action=query", None),
        ("https://www.flickr.com/photos/someone/albums/72157", None),
        ("https://www.flickr.com/groups/eurorack/", None),
        ("https://example.com/wiki/File:A.jpg", None),
        ("https://upload.wikimedia.org/wikipedia/commons/a/ab/A.jpg", None),
        ("ftp://commons.wikimedia.org/wiki/File:A.jpg", None),
    ],
)
def test_normalize_photo_url(url, expected):
    assert photos.normalize_photo_url(url) == expected


def test_downloader_refuses_other_hosts_and_types(tmp_path):
    calls: list[str] = []

    def transport(request):
        calls.append(request.url)
        if request.url.endswith("/robots.txt"):
            return HttpResponse(404, b"", {})
        return HttpResponse(200, b"<html>", {"content-type": "text/html"})

    dl = photos.ImageDownloader(tmp_path / "images", transport=transport, sleeper=lambda s: None)
    assert dl.download("https://example.com/a.jpg")["reason"] == "image_host_not_allowed"
    assert dl.download("http://upload.wikimedia.org/a.jpg")["reason"] == "image_host_not_allowed"
    assert calls == []
    assert dl.download(COMMONS_IMAGE)["reason"] == "mime_not_allowed"
    assert not (tmp_path / "images").exists()


def test_downloader_respects_robots_spacing_and_size(tmp_path):
    clock = {"t": 0.0}
    slept: list[float] = []

    def sleeper(seconds):
        slept.append(seconds)
        clock["t"] += seconds

    def transport(request):
        if request.url == "https://upload.wikimedia.org/robots.txt":
            return HttpResponse(200, b"User-agent: *\nDisallow: /private/\n", {})
        if "big" in request.url:
            return HttpResponse(200, JPEG + b"x" * 64, {"content-type": "image/jpeg"})
        return HttpResponse(200, JPEG, {"content-type": "image/jpeg"})

    dl = photos.ImageDownloader(
        tmp_path / "images",
        transport=transport,
        sleeper=sleeper,
        monotonic=lambda: clock["t"],
        max_bytes=len(JPEG) + 10,
    )
    assert (
        dl.download("https://upload.wikimedia.org/private/a.jpg")["reason"] == "robots_disallowed"
    )
    ok = dl.download(COMMONS_IMAGE)
    assert ok["ok"] and ok["path"] == f"images/{ok['sha256']}.jpg"
    assert (tmp_path / ok["path"]).read_bytes() == JPEG
    assert dl.download("https://upload.wikimedia.org/big.jpg")["reason"] == "too_large"
    assert slept and all(abs(s - photos.HOST_INTERVAL_S) < 1e-9 for s in slept)


# --------------------------------------------------------------------------- run harness


FUTURE = "2099-01-01T00:00:00Z"


def _entry(**over):
    entry = {
        "id": photos.APPROVAL_ID,
        "approver": "owner",
        "expires_at": FUTURE,
        "brands": [photos.APPROVAL_ID],
        "cap_fetches": 300,
        "cap_credits": 300,
        "ledger_baseline_fetches": 2569,
        "ledger_baseline_credits": 1149,
    }
    entry.update(over)
    return entry


class World:
    """Fake network: DuckDuckGo finds nothing, context.dev returns the result URLs, pages and images are fixtures."""

    def __init__(
        self, tmp_path: Path, entries: list | None = None, ledger: dict | None = None
    ) -> None:
        self.tmp = tmp_path
        self.calls: list[HttpRequest] = []
        self.search_urls = [
            COMMONS_OK,
            COMMONS_GFDL,
            FLICKR_OK + "in/photostream/",
            FLICKR_NC,
            "https://example.com/plaits-review",
            "https://commons.wikimedia.org/wiki/Category:Eurorack",
        ]
        (tmp_path / "approvals.json").write_text(
            json.dumps({"entries": [_entry()] if entries is None else entries})
        )
        (tmp_path / "ledger.json").write_text(
            json.dumps(
                ledger
                or {
                    "paid_fetches": 2569,
                    "credits_by_backend": {"context_dev": 1116.0, "firecrawl": 33.0},
                }
            )
        )
        self.pages = {
            COMMONS_OK: commons_html(
                "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0"
            ),
            COMMONS_GFDL: commons_html("GFDL", "http://www.gnu.org/copyleft/fdl.html"),
            FLICKR_OK: flickr_html("https://creativecommons.org/licenses/by/2.0/"),
            FLICKR_NC: flickr_html("https://creativecommons.org/licenses/by-nc/2.0/"),
        }

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        url = request.url
        if url.endswith("/robots.txt"):
            return HttpResponse(404, b"", {})
        if url.startswith("https://lite.duckduckgo.com/"):
            return HttpResponse(200, b"<html>no results</html>", {})
        if url == "https://api.context.dev/v1/web/search":
            body = {
                "results": [{"url": u} for u in self.search_urls],
                "key_metadata": {"credits_consumed": 1},
            }
            return HttpResponse(200, json.dumps(body).encode(), {})
        if url in self.pages:
            return HttpResponse(200, self.pages[url].encode(), {"content-type": "text/html"})
        if url in (COMMONS_IMAGE, FLICKR_IMAGE_K):
            return HttpResponse(200, JPEG + url.encode(), {"content-type": "image/jpeg"})
        return HttpResponse(404, b"", {})

    def factory(self, **kwargs):
        return CatalogScraper(
            cache_dir=self.tmp / "cache",
            ledger_path=self.tmp / "ledger.json",
            approvals_path=self.tmp / "approvals.json",
            transport=self,
            sleeper=lambda s: None,
            wall_clock=lambda: 1_800_000_000.0,
            resolve_hosts=False,
            **kwargs,
        )

    def downloader(self, out: Path):
        return photos.ImageDownloader(out / "images", transport=self, sleeper=lambda s: None)

    def run(self, identities: list[dict], out: Path, **kwargs):
        return photos.run_search(
            identities,
            out,
            search_scraper_factory=self.factory,
            page_scraper_factory=self.factory,
            downloader=self.downloader(out),
            wall_clock=lambda: 1_800_000_000.0,
            log=lambda line: None,
            **kwargs,
        )


IDENTITY = {
    "brand": "Mutable Instruments",
    "name": "Plaits",
    "slug": "mutable-instruments-plaits",
    "manufacturer_url": "https://pichenettes.github.io/mutable-instruments-documentation/modules/plaits/",
}


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "ctx-test-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key-never-used")


def _rows(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out / "candidates.jsonl").read_text().splitlines()]


def test_run_end_to_end_counts_rows_and_queue_shape(tmp_path, keys):
    world = World(tmp_path)
    out = tmp_path / "out"
    summary = world.run([IDENTITY], out)
    counts = summary["counts"]
    assert counts["searched"] == 1 and counts["paid_searches"] == 1
    assert counts["results"] == 6 and counts["allowed_host_results"] == 4
    assert counts["license_accepted"] == 2 and counts["downloaded"] == 1
    # The accepted Flickr page is titled "Make Noise Maths in rack": it does not name Plaits.
    assert counts["identity_not_named"] == 1
    assert counts["license_excluded"] == {"license_not_allowed": 1, "non_commercial": 1}
    assert json.loads((out / "summary.json").read_text())["counts"] == counts

    rows = {row["source_url"]: row for row in _rows(out)}
    assert set(rows) == {COMMONS_OK, COMMONS_GFDL, FLICKR_OK, FLICKR_NC}
    ok = rows[COMMONS_OK]
    assert ok["kind"] == "image_asset" and ok["rights_status"] == "RIGHTS_CONFIRMED"
    assert ok["rights_basis"].startswith(
        "CC-BY-SA-4.0 (https://creativecommons.org/licenses/by-sa/4.0)"
    )
    assert "Jane Doe" in ok["rights_basis"]
    assert ok["ground_truth_status"] == "UNVERIFIED" and ok["annotation_status"] == "DISCOVERED"
    assert ok["reviewer"] is None and ok["cohort"] is None and ok["partition"] is None
    assert ok["proposed_cohort"] == "installed_rack"
    assert [s["kind"] for s in ok["identity_sources"]] == ["photo_page_text", "manufacturer_page"]
    assert ok["identity_sources"][0]["matched_field"] == "title"
    assert ok["identity_sources"][1]["url"] == IDENTITY["manufacturer_url"]
    assert (out / ok["image_path"]).is_file()
    assert rows[FLICKR_NC]["rights_status"] == "RIGHTS_RESTRICTED"
    assert rows[FLICKR_NC]["kind"] == "image_reference" and rows[FLICKR_NC]["image_sha256"] is None
    assert rows[COMMONS_GFDL]["exclusion_reason"] == "license_not_allowed"
    other = rows[FLICKR_OK]
    assert other["rights_status"] == "RIGHTS_CONFIRMED"
    assert other["exclusion_reason"] == "identity_not_named"
    assert other["kind"] == "image_reference" and other["proposed_expected_choice"] is None
    assert other["download_status"] == "not_attempted" and other["image_path"] is None
    assert other["identity_sources"][0]["matched_field"] is None
    for row in rows.values():
        assert row["ground_truth_status"] not in {"OPERATOR_VERIFIED", "TWO_SOURCE_VERIFIED"}
        assert row["annotation_status"] != "REVIEWED"

    # The promotion queue reads these files as they are.
    modules = [json.loads(line) for line in (out / "modules.jsonl").read_text().splitlines()]
    result = queue.build_queue(_rows(out), modules)
    assert result["rights_cleared"] == 1 and result["admitted"] == 0
    for item in result["items"]:
        assert item["asset_hash"].startswith("sha256:") and len(item["asset_hash"]) == 71
        assert item["identity_ref"] == "mutable-instruments-plaits"
        assert item["proposed_identity"] == "mutable-instruments-plaits"
        assert item["manufacturer"] == "Mutable Instruments"
        assert item["license"] == "CC-BY-SA-4.0"
        assert item["ground_truth_status"] == "UNVERIFIED"


def test_never_calls_firecrawl_and_restores_the_key(tmp_path, keys):
    world = World(tmp_path)
    world.search_urls = [
        COMMONS_OK
    ]  # fewer than the limit, so the router would try the next paid backend
    world.run([IDENTITY], tmp_path / "out")
    assert world.calls, "the fake network was used"
    assert not any("firecrawl" in c.url for c in world.calls)
    assert sum(1 for c in world.calls if "api.context.dev" in c.url) == 1
    assert os.environ["FIRECRAWL_API_KEY"] == "fc-test-key-never-used"
    receipts = (tmp_path / "out" / "receipts.jsonl").read_text()
    assert '"method": "firecrawl"' not in receipts
    assert "fc-test-key" not in receipts and "ctx-test-key" not in receipts


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [_entry(expires_at="2000-01-01T00:00:00Z")],
        [_entry(approver="")],
        [_entry(id="other", brands=["Other"])],
    ],
)
def test_refuses_before_any_request_when_the_gate_refuses(tmp_path, keys, entries):
    world = World(tmp_path, entries=entries)
    with pytest.raises(photos.Refused):
        world.run([IDENTITY], tmp_path / "out")
    assert world.calls == []
    assert not (tmp_path / "out").exists()


def test_refuses_when_the_approval_is_used_up_and_caps_max_searches(tmp_path, keys):
    spent = {
        "paid_fetches": 2569 + 300,
        "credits_by_backend": {"context_dev": 1116.0 + 300, "firecrawl": 33.0},
    }
    world = World(tmp_path, ledger=spent)
    with pytest.raises(photos.Refused):
        world.run([IDENTITY], tmp_path / "out")
    assert world.calls == []

    nearly = {
        "paid_fetches": 2569 + 299,
        "credits_by_backend": {"context_dev": 1116.0 + 299, "firecrawl": 33.0},
    }
    world = World(tmp_path, ledger=nearly)
    others = [dict(IDENTITY, slug=f"mutable-instruments-plaits-{n}") for n in range(3)]
    summary = world.run(others, tmp_path / "out")
    assert summary["max_searches"] == 1 and summary["counts"]["searched"] == 1
    with pytest.raises(photos.Refused):
        world.run([IDENTITY], tmp_path / "out2", max_searches=301)


@pytest.mark.parametrize(
    "inside", [ROOT, ROOT / "work" / "photos", ROOT / "fixtures" / "vision_eval"]
)
def test_out_dir_inside_the_repo_is_refused_before_any_request(tmp_path, keys, inside):
    world = World(tmp_path)
    with pytest.raises(photos.Refused):
        world.run([IDENTITY], inside)
    assert world.calls == []


def test_out_dir_inside_any_git_checkout_is_refused(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(photos.Refused):
        photos.check_out_dir(tmp_path / "repo" / "corpus")
    assert photos.check_out_dir(tmp_path / "corpus") == (tmp_path / "corpus").resolve()


def test_image_bytes_land_only_in_the_out_dir(tmp_path, keys):
    world = World(tmp_path)
    out = tmp_path / "out"
    world.run([IDENTITY], out)
    written = sorted(
        p for p in tmp_path.rglob("*") if p.is_file() and p.read_bytes().startswith(JPEG[:3])
    )
    assert written and all(p.parent == out / "images" for p in written)
    assert not any(str(p).startswith(str(ROOT)) for p in written)


# --------------------------------------------------------------------------- identity check


def _page(title: str, description: str = ""):
    return photos.PhotoPage(
        host="commons",
        url="https://commons.wikimedia.org/wiki/File:x.jpg",
        title=title,
        description=description,
        license=photos.License(accepted=True, name="CC0-1.0", url=None, reason=None),
        author="A",
        image_url=None,
    )


@pytest.mark.parametrize(
    "brand, name, title, description, expected",
    [
        ("Mutable Instruments", "Plaits", "File:Mutable Instruments Plaits.jpg", "", "title"),
        ("Mutable Instruments", "Plaits", "File:Plaits.jpg", "Mutable module", "title"),
        ("Verbos Electronics", "Complex Oscillator",
         "File:Verbos Electronics - Complex Oscillator - 2014 NAMM Show.jpg", "", "title"),
        ("Doepfer", "A-102", "File:Doepfer Eurorack (A-101-2,A-102,A-103).jpg", "", "title"),
        ("Instruo", "C-is-2", "File:Instruo Cis2.jpg", "", "title"),
        # Live false positives from the 2026-11-02 run: the module name alone, no maker.
        ("WMD", "Kraken", "File:Kraken Supercomputer (4100442871).jpg", "", None),
        ("Xaoc Devices", "Batumi", "File:Europe Square, Batumi.jpg", "", None),
        ("2hp", "Arp", "File:ARP 2601 v2.0 black-on-orange.jpg", "", None),
        # A generic word of the maker's name does not stand for the maker.
        ("Verbos Electronics", "Noise Filter", "File:Noise Filter.svg", "electronics", None),
        # Part of a model number, or short words scattered in a description, are not the module.
        ("Doepfer", "A-101-1", "File:Doepfer Eurorack (A-101-2,A-106-1).jpg", "", None),
        ("Instruo", "C-is-2", "File:Instruo.png", "this is a case with 2 rows", None),
        ("Make Noise", "Maths", "File:Eurorack Modular Synthesizer.jpg", "a rack", None),
    ],
)
def test_identity_match_needs_the_maker_and_the_module_phrase(brand, name, title, description, expected):
    identity = {"brand": brand, "name": name}
    assert photos.identity_match(identity, _page(title, description)) == expected


def test_refilter_drops_rows_that_do_not_name_their_module(tmp_path, keys, capsys):
    world = World(tmp_path)
    out = tmp_path / "out"
    world.run([IDENTITY], out)
    rows = _rows(out)
    # Rewrite one row as an older run would have left it: kept as an asset for Plaits.
    stale = next(r for r in rows if r["source_url"] == FLICKR_OK)
    stale.update(kind="image_asset", exclusion_reason=None,
                 proposed_expected_choice=IDENTITY["slug"], rights_basis="x")
    src = tmp_path / "old.jsonl"
    src.write_text("".join(json.dumps(r) + "\n" for r in rows))
    dst = tmp_path / "new.jsonl"
    assert photos.main(["refilter", "--candidates", str(src), "--out", str(dst)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["rows"] == len(rows) and report["named"] == 2
    new = {r["source_url"]: r for r in map(json.loads, dst.read_text().splitlines())}
    assert new[FLICKR_OK]["kind"] == "image_reference"
    assert new[FLICKR_OK]["exclusion_reason"] == "identity_not_named"
    assert new[FLICKR_OK]["proposed_expected_choice"] is None
    assert new[COMMONS_OK]["kind"] == "image_asset"
    assert new[COMMONS_GFDL]["exclusion_reason"] == "license_not_allowed"
    assert queue.build_queue(list(new.values()), [])["rights_cleared"] == 1


# --------------------------------------------------------------------------- starter


def test_starter_writes_known_slugs_and_reports_missing(tmp_path):
    known = photos.catalog_identities()
    slug = next(s for s, row in known.items() if row["manufacturer_url"])
    picked, missing = photos.write_starter(
        [slug, "no-such-module-slug"], tmp_path / "identities.json"
    )
    assert missing == ["no-such-module-slug"]
    written = json.loads((tmp_path / "identities.json").read_text())
    assert written == picked and written[0]["slug"] == slug
    assert set(written[0]) == {"brand", "name", "slug", "manufacturer_url"}
    assert photos.load_identities(tmp_path / "identities.json") == written


def test_starter_skips_retired_slugs():
    retired = json.loads(
        (ROOT / "data/synth-catalog/overlays/catalog-retirements-v1.json").read_text()
    )["rows"]
    known = photos.catalog_identities()
    assert all(row["slug"] not in known for row in retired)
