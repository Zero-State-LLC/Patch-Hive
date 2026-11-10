#!/usr/bin/env python3
"""Check catalog rows with no access basis and write overlays/access-basis-v1.json (owner decision 53).

A row earns `official_publication` only under ADR 0002's conditions: its page is on the maker's own
site, robots.txt lets our crawler read that page, and the maker hasn't opted out. Each row keeps
which checks it passed, and a row that fails stays out with its reason.

`--catalog` takes saved rows from `GET /api/modules/catalog`, from each database. Anonymous reads
leave out `unknown` rows, which is all this needs. CatalogCandidate rows aren't listed here: they
are ModularGrid-derived, so the loader tags them by source instead of the repo naming them. A rerun
checks only the rows still without a basis and keeps the rows the overlay already tags, which a load
from empty still needs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from catalog_scrape import USER_AGENT, parse_robots, permission_basis, robots_file_absent  # noqa: E402

SOURCES = ROOT / "data" / "synth-catalog" / "maker-sources.json"
OVERLAY = ROOT / "data" / "synth-catalog" / "overlays" / "access-basis-v1.json"
URL_CORRECTIONS = ROOT / "data" / "synth-catalog" / "provenance" / "catalog-url-corrections-v1.json"
MAKER_ROW_SOURCES = ("ManufacturerCrawl", "ManufacturerVerified")
# Hosts that serve many makers from subdomains: the whole host is the maker's, the domain isn't.
SHARED_PLATFORMS = (
    "bigcartel.com",
    "blogspot.com",
    "company.site",
    "github.io",
    "myshopify.com",
    "wixsite.com",
    "wordpress.com",
)
# Read by hand on 2026-11-05: the host's name doesn't carry the brand, and the site is the maker's.
REVIEWED_HOSTS = {
    ("Mutable Instruments", "pichenettes.github.io"): "the maker's documentation site",
    ("BÈSIA Modular", "besia.bigcartel.com"): "the maker's store, titled with its name",
    ("Synthetic Sound Labs", "steamsynth.com"): "the maker's site, titled with its name",
    ("Unknown Devices", "unwn.dev"): "the maker's site, titled with its name",
}


def url_host(url: str | None) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def site(host: str) -> str:
    """The part of a host that identifies one owner."""
    parts = host.split(".")
    second_level = len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "ac") and len(parts[-1]) == 2
    domain = ".".join(parts[-3:] if second_level else parts[-2:])
    return host if domain in SHARED_PLATFORMS else domain


def squash(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def brand_in_host(brand: str, host: str) -> bool:
    name, label = squash(brand), squash(site(host).split(".")[0])
    return len(name) >= 3 and len(label) >= 3 and (name in squash(site(host)) or label in name)


def read_robots(origin: str) -> tuple[int, str]:
    """(status, body). 0 is no answer. Only a 200 or a 404 may be read past, as in catalog_scrape."""
    request = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT})
    for _ in range(2):  # one retry, so a passing timeout doesn't leave a maker out
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return response.status, response.read(500_000).decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(500_000).decode("utf-8", "ignore")
        except (OSError, ValueError):
            continue
    return 0, ""


def robots_answer(answers: dict[str, tuple[int, str]], url: str) -> str | None:
    """None when robots.txt lets us read this page, otherwise why not."""
    parts = urlsplit(url)
    status, body = answers[f"{parts.scheme}://{parts.netloc}"]
    if robots_file_absent(status, body.encode("utf-8")):
        return None
    if status != 200:
        return f"robots_unavailable_{status}"
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    return None if parse_robots(body, USER_AGENT, path or "/") else "robots_disallowed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, default=OVERLAY)
    args = parser.parse_args()

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    rows: dict[str, dict] = {}
    for path in args.catalog:
        for row in json.loads(path.read_text(encoding="utf-8")):
            rows.setdefault(row["slug"], row)
    # A row whose reviewed correction moves it to the maker's page is checked at that page.
    for correction in json.loads(URL_CORRECTIONS.read_text(encoding="utf-8"))["rows"]:
        if correction["slug"] in rows:
            rows[correction["slug"]]["manufacturer_url"] = correction["fields"][0]["value"]

    listed: dict[str, set[str]] = {}
    for brand, entry in [*sources["homepages"].items(), *sources["adapters"].items()]:
        if entry.get("homepage") and entry.get("status") != "rejected":
            listed.setdefault(brand, set()).add(site(url_host(entry["homepage"])))
    official: dict[str, set[str]] = {}
    for row in rows.values():
        if row.get("access_basis") == "official_publication" and row.get("manufacturer_url"):
            official.setdefault(row["brand"], set()).add(site(url_host(row["manufacturer_url"])))

    todo = [r for r in rows.values() if r.get("access_basis") is None and r.get("source") in MAKER_ROW_SOURCES]
    origins = sorted({"{0.scheme}://{0.netloc}".format(urlsplit(r["manufacturer_url"])) for r in todo})
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = dict(zip(origins, pool.map(read_robots, origins)))

    tagged, left_out = [], []
    for row in sorted(todo, key=lambda r: r["slug"]):
        brand, host = row["brand"], url_host(row["manufacturer_url"])
        checks = [
            name
            for name, passed in (
                ("maker_sources", site(host) in listed.get(brand, ())),
                ("official_rows", site(host) in official.get(brand, ())),
                ("brand_in_host", brand_in_host(brand, host)),
                ("reviewed", (brand, host) in REVIEWED_HOSTS),
            )
            if passed
        ]
        reason = (
            ("maker_opted_out" if permission_basis(sources, brand) != "official_publication" else None)
            or ("maker_site_not_confirmed" if not checks else None)
            or robots_answer(answers, row["manufacturer_url"])
        )
        identity = {"slug": row["slug"], "brand": brand, "name": row["name"], "host": host}
        if reason:
            left_out.append({**identity, "reason": reason})
        else:
            tagged.append({**identity, "access_basis": "official_publication", "checks": checks})

    checked = {row["slug"] for row in [*tagged, *left_out]}
    if args.out.is_file():
        earlier = json.loads(args.out.read_text(encoding="utf-8"))["rows"]
        tagged = sorted([*tagged, *(row for row in earlier if row["slug"] not in checked)], key=lambda r: r["slug"])
    args.out.write_text(
        json.dumps(
            {
                "decision": "docs/evidence/OWNER_DECISIONS_2026-11-04.md decision 53, under docs/adr/0002",
                "checked": "2026-11-05",
                "rows": tagged,
                "left_out": left_out,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{len(todo)} rows, {len(origins)} sites: {len(tagged)} tagged, {len(left_out)} left out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
