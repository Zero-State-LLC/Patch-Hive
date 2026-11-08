"""Spec 009 T070b: corpus photos stay on Wikimedia Commons, pinned here by their hash."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "fetch_corpus_photos.py"
PHOTO = b"a photo of a whole Rig"
URL = "https://upload.wikimedia.org/wikipedia/commons/6/64/Case.jpg"


def _load():
    spec = importlib.util.spec_from_file_location("_fetch_corpus_photos", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_corpus_photos = _load()


def _case(url: str = URL, file: str = "commons-001.jpg", photo: bytes = PHOTO) -> dict:
    return {
        "case_id": file,
        "image_asset_hashes": [f"sha256:{hashlib.sha256(photo).hexdigest()}"],
        "asset_source": {"file": file, "url": url},
    }


def _recording(answer: bytes) -> tuple:
    asked: list[str] = []

    def fetch(url: str) -> bytes:
        asked.append(url)
        return answer

    return fetch, asked


def _run(cases: list[dict], out: Path, answer: bytes = PHOTO) -> tuple[list, list[str]]:
    fetch, asked = _recording(answer)
    done = fetch_corpus_photos.fetch_photos({"cases": cases}, out, fetch=fetch, pause=lambda: None)
    return done, asked


def _refused(cases: list[dict], out: Path, answer: bytes = PHOTO) -> tuple[str, list[str]]:
    fetch, asked = _recording(answer)
    with pytest.raises(fetch_corpus_photos.PhotoRefused) as refused:
        fetch_corpus_photos.fetch_photos({"cases": cases}, out, fetch=fetch, pause=lambda: None)
    return refused.value.code, asked


def test_a_photo_that_matches_its_hash_lands_under_its_name(tmp_path: Path) -> None:
    done, asked = _run([_case()], tmp_path)

    assert (tmp_path / "commons-001.jpg").read_bytes() == PHOTO
    assert done == [("commons-001.jpg", "fetched")]
    assert asked == [URL]


def test_a_photo_that_has_changed_on_commons_is_refused_and_not_kept(tmp_path: Path) -> None:
    code, _ = _refused([_case()], tmp_path, answer=b"a different photo")

    assert code == "PHOTO_HASH_MISMATCH"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://upload.wikimedia.org/wikipedia/commons/6/64/Case.jpg",
        "https://example.invalid/Case.jpg",
        "https://upload.wikimedia.org.example.invalid/Case.jpg",
        "https://commons.wikimedia.org/wiki/File:Case.jpg",
    ],
)
def test_only_the_commons_file_host_is_asked(tmp_path: Path, url: str) -> None:
    code, asked = _refused([_case(url=url)], tmp_path)

    assert code == "PHOTO_SOURCE_NOT_ALLOWED"
    assert asked == []


@pytest.mark.parametrize(
    "file", ["../commons-001.jpg", "a/commons-001.jpg", "", "..", "/etc/x.jpg"]
)
def test_a_file_name_cannot_leave_the_folder(tmp_path: Path, file: str) -> None:
    code, asked = _refused([_case(file=file)], tmp_path / "out")

    assert code == "PHOTO_NAME_INVALID"
    assert asked == []


def test_a_photo_already_there_is_not_asked_for_again(tmp_path: Path) -> None:
    (tmp_path / "commons-001.jpg").write_bytes(PHOTO)

    done, asked = _run([_case()], tmp_path)

    assert done == [("commons-001.jpg", "present")]
    assert asked == []


def test_a_wrong_file_already_there_is_replaced(tmp_path: Path) -> None:
    (tmp_path / "commons-001.jpg").write_bytes(b"something else")

    done, _ = _run([_case()], tmp_path)

    assert (tmp_path / "commons-001.jpg").read_bytes() == PHOTO
    assert done == [("commons-001.jpg", "fetched")]


def test_a_case_with_no_commons_source_is_left_alone(tmp_path: Path) -> None:
    own = {"case_id": "own-rig", "image_asset_hashes": ["sha256:" + "a" * 64]}

    done, asked = _run([own], tmp_path)

    assert done == []
    assert asked == []


def test_the_folder_is_made_when_it_is_missing(tmp_path: Path) -> None:
    out = tmp_path / "photos" / "commons"

    _run([_case()], out)

    assert (out / "commons-001.jpg").is_file()


def test_two_cases_cannot_share_a_file_name(tmp_path: Path) -> None:
    code, asked = _refused([_case(), _case(photo=b"another Rig")], tmp_path)

    assert code == "PHOTO_NAME_DUPLICATE"
    assert asked == []


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError(URL, 404, "Not Found", None, None),  # type: ignore[arg-type]
        urllib.error.URLError("no route"),
        TimeoutError("timed out"),
        http.client.IncompleteRead(b""),
    ],
)
def test_a_photo_that_cannot_be_fetched_is_refused_in_words(monkeypatch, failure) -> None:
    def unreachable(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(fetch_corpus_photos.urllib.request, "urlopen", unreachable)

    with pytest.raises(fetch_corpus_photos.PhotoRefused) as refused:
        fetch_corpus_photos.download(URL)
    assert refused.value.code == "PHOTO_FETCH_FAILED"
