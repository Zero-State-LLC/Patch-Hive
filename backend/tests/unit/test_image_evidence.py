import io

import pytest
from PIL import Image

from evidence.images import SignatureImageScanner, UnsafeImageError, prepare_image_evidence


def _jpeg(*, metadata: bool = False) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (32, 24), (40, 80, 120))
    image.save(output, format="JPEG", exif=b"private-metadata" if metadata else b"")
    return output.getvalue()


def test_a_jpeg_comment_is_removed() -> None:
    output = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(output, format="JPEG", comment=b"private-comment")
    assert b"private-comment" in output.getvalue()

    prepared = prepare_image_evidence(
        output.getvalue(), declared_media_type="image/jpeg", scanner=SignatureImageScanner()
    )

    assert b"private-comment" not in prepared.content
    with Image.open(io.BytesIO(prepared.content)) as image:
        assert "comment" not in image.info


def test_image_is_reencoded_and_metadata_removed() -> None:
    original = _jpeg(metadata=True)
    prepared = prepare_image_evidence(
        original, declared_media_type="image/jpeg", scanner=SignatureImageScanner()
    )
    assert prepared.media_type == "image/jpeg"
    assert (prepared.width, prepared.height) == (32, 24)
    assert prepared.content != original
    with Image.open(io.BytesIO(prepared.content)) as image:
        assert not image.getexif()


def test_mime_must_match_decoded_signature() -> None:
    with pytest.raises(UnsafeImageError, match="IMAGE_MIME_MISMATCH"):
        prepare_image_evidence(
            _jpeg(), declared_media_type="image/png", scanner=SignatureImageScanner()
        )


@pytest.mark.parametrize("content", [b"<svg><script/></svg>", b"<!doctype html><h1>not image</h1>"])
def test_active_content_is_rejected_before_decode(content: bytes) -> None:
    with pytest.raises(UnsafeImageError, match="IMAGE_SCAN_REJECTED"):
        prepare_image_evidence(
            content, declared_media_type="image/png", scanner=SignatureImageScanner()
        )
