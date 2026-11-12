#!/usr/bin/env python3
"""Fetch the evaluation corpus's Wikimedia Commons photos and check them against their hashes.

The photos stay on Commons and aren't committed. The manifest pins each one by SHA-256, so a
photo that has changed on Commons is refused rather than scored against labels made for
another picture. A case with no ``asset_source``, such as a photo of the owner's own Rig, is
left alone.

Usage (repo root):
  python scripts/fetch_corpus_photos.py --out ~/patchhive-corpus/photos
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

ALLOWED_HOST = "upload.wikimedia.org"
USER_AGENT = "PatchHive-corpus-fetch/1.0 (https://patch-hive.com)"
MAX_BYTES = 64 * 1024 * 1024


class PhotoRefused(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:  # nosec B310
            data = response.read(MAX_BYTES + 1)
    except (OSError, http.client.HTTPException) as failure:
        raise PhotoRefused("PHOTO_FETCH_FAILED", f"{url}: {failure}") from None
    if len(data) > MAX_BYTES:
        raise PhotoRefused("PHOTO_TOO_LARGE", url)
    return data


def _source(case: dict) -> tuple[str, str, str]:
    """The photo's file name, address and expected hash, once they're all safe to use."""
    source = case["asset_source"]
    file, url = str(source.get("file") or ""), str(source.get("url") or "")
    if not file or file in {".", ".."} or Path(file).name != file or "\\" in file:
        raise PhotoRefused("PHOTO_NAME_INVALID", repr(file))
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        raise PhotoRefused("PHOTO_SOURCE_NOT_ALLOWED", url)
    hashes = case.get("image_asset_hashes") or []
    if len(hashes) != 1 or not str(hashes[0]).startswith("sha256:"):
        raise PhotoRefused("PHOTO_HASH_MISSING", file)
    return file, url, str(hashes[0]).removeprefix("sha256:")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_photos(
    manifest: dict,
    out: Path,
    *,
    fetch: Callable[[str], bytes] = download,
    pause: Callable[[], None] = lambda: time.sleep(1),
) -> list[tuple[str, str]]:
    """Put each sourced photo in ``out``. Answers (file, "fetched" or "present") for each."""
    # Every source is checked before anything is asked for.
    sources = [_source(case) for case in manifest["cases"] if case.get("asset_source")]
    files = [file for file, _, _ in sources]
    if len(set(files)) != len(files):
        raise PhotoRefused("PHOTO_NAME_DUPLICATE")
    out.mkdir(parents=True, exist_ok=True)
    done: list[tuple[str, str]] = []
    fetched_any = False
    for file, url, expected in sources:
        path = out / file
        if path.is_file() and _digest(path.read_bytes()) == expected:
            done.append((file, "present"))
            continue
        if fetched_any:
            pause()
        data = fetch(url)
        fetched_any = True
        if _digest(data) != expected:
            raise PhotoRefused("PHOTO_HASH_MISMATCH", file)
        partial = path.with_name(f"{file}.part")
        partial.write_bytes(data)
        partial.replace(path)
        done.append((file, "fetched"))
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default="fixtures/vision_eval/pilot-manifest.json")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    try:
        for file, status in fetch_photos(manifest, args.out.expanduser()):
            print(f"{status}: {file}")
    except PhotoRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
