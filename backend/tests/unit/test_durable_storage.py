"""Durable storage mirror for files recorded by local path (spec 006 T055)."""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.orm import Session

import core.storage as storage
from canon.contracts import ExportRequest
from canon.exports import request_export
from canon.fulfillment import fulfill_export, pack_dir_for_export
from canon.models import ImageAssetRecord
from core.storage import LocalFileStore, S3FileStore, StorageError, get_file_store
from racks.models import Rack
from tests.unit.test_pack_download import NOW, _auth_headers, _client, _seed


class _Missing(Exception):
    def __init__(self) -> None:
        super().__init__("missing")
        self.response = {"Error": {"Code": "NoSuchKey"}}


class FakeS3:
    """In-memory stand-in for the boto3 S3 client calls core.storage makes."""

    def __init__(self, page_size: int = 1000) -> None:
        self.objects: dict[str, bytes] = {}
        self.page_size = page_size
        self.fail_writes = False
        self.fail_deletes = 0  # number of upcoming delete_object calls that fail
        self.delete_calls = 0

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        if self.fail_writes:
            raise ConnectionError("down")
        self.objects[Key] = bytes(Body)

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise _Missing()
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.delete_calls += 1
        if self.fail_deletes > 0:
            self.fail_deletes -= 1
            raise ConnectionError("down")
        self.objects.pop(Key, None)

    def list_objects_v2(self, *, Bucket: str, Prefix: str, ContinuationToken: str = "0") -> dict:
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken)
        page = keys[start : start + self.page_size]
        more = start + self.page_size < len(keys)
        out: dict = {"Contents": [{"Key": k} for k in page], "IsTruncated": more}
        if more:
            out["NextContinuationToken"] = str(start + self.page_size)
        return out


@pytest.fixture()
def fake_s3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeS3:
    import core.config as config_mod

    fake = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", lambda *args: fake)
    monkeypatch.setattr(config_mod.settings, "export_dir", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "export_store_root", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "storage_backend", "s3")
    monkeypatch.setattr(config_mod.settings, "s3_endpoint_url", "https://r2.example.invalid")
    monkeypatch.setattr(config_mod.settings, "s3_bucket", "patchhive-test")
    monkeypatch.setattr(config_mod.settings, "s3_access_key_id", "id")
    monkeypatch.setattr(config_mod.settings, "s3_secret_access_key", "secret")
    return fake


def _store(tmp_path: Path, fake: FakeS3, prefix: str = "") -> S3FileStore:
    return S3FileStore(fake, "b", {"exports": tmp_path / "exports"}, prefix=prefix)


def test_local_backend_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "storage_backend", "local")
    assert isinstance(get_file_store(), LocalFileStore)


def test_s3_backend_fails_closed_when_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "storage_backend", "s3")
    monkeypatch.setattr(config_mod.settings, "s3_bucket", "")
    with pytest.raises(StorageError) as err:
        get_file_store()
    assert err.value.code == storage.NOT_CONFIGURED


def test_unknown_backend_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "storage_backend", "ftp")
    with pytest.raises(StorageError):
        get_file_store()


def test_keys_are_root_relative_and_paths_outside_roots_are_refused(tmp_path: Path) -> None:
    store = _store(tmp_path, FakeS3(), prefix="/staging/")
    assert store.key_for(tmp_path / "exports" / "evidence" / "a.jpg") == (
        "staging/exports/evidence/a.jpg"
    )
    with pytest.raises(StorageError) as err:
        store.key_for(tmp_path / "elsewhere.jpg")
    assert err.value.code == storage.PATH_OUTSIDE_ROOTS


def test_persist_then_restore_after_local_loss(tmp_path: Path) -> None:
    fake = FakeS3()
    store = _store(tmp_path, fake)
    path = tmp_path / "exports" / "evidence" / "a.jpg"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"jpeg-bytes")
    store.persist(path)

    path.unlink()
    assert store.ensure_local(path) is True
    assert path.read_bytes() == b"jpeg-bytes"
    assert store.ensure_local(tmp_path / "exports" / "evidence" / "missing.jpg") is False


def test_write_failure_raises_a_stable_code(tmp_path: Path) -> None:
    fake = FakeS3()
    fake.fail_writes = True
    store = _store(tmp_path, fake)
    path = tmp_path / "exports" / "x.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    with pytest.raises(StorageError) as err:
        store.persist(path)
    assert err.value.code == storage.WRITE_FAILED


def test_delete_removes_both_copies(tmp_path: Path) -> None:
    fake = FakeS3()
    store = _store(tmp_path, fake)
    path = tmp_path / "exports" / "x.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    store.persist(path)
    assert store.delete(path) is True
    assert not path.exists()
    assert fake.objects == {}


def test_tree_round_trip_follows_pagination(tmp_path: Path) -> None:
    fake = FakeS3(page_size=2)
    store = _store(tmp_path, fake)
    pack = tmp_path / "exports" / "design_packs" / "exp-1"
    (pack / "sub").mkdir(parents=True)
    for name in ("PatchBook.pdf", "manifest.json", "sub/companion.pdf"):
        (pack / name).write_bytes(name.encode())
    store.persist_tree(pack)
    assert len(fake.objects) == 3

    shutil.rmtree(pack)
    assert store.ensure_local_tree(pack) is True
    assert (pack / "sub" / "companion.pdf").read_bytes() == b"sub/companion.pdf"


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (128, 96), (20, 40, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def test_evidence_upload_is_durable_and_restorable(
    db_session: Session, sample_rack_basic: Rack, fake_s3: FakeS3
) -> None:
    from main import app

    client = _client(db_session)
    resp = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=[("files", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"retention_days": "14", "consent_provider_processing": "false"},
    )
    app.dependency_overrides.clear()
    assert resp.status_code == 201, resp.text
    record = db_session.get(ImageAssetRecord, resp.json()["uploaded"][0]["id"])
    path = Path(record.storage_path)
    assert [k for k in fake_s3.objects if k.startswith("exports/evidence/")]

    path.unlink()  # the container's disk was wiped
    assert get_file_store().ensure_local(path) is True
    assert path.exists()


def test_evidence_upload_refuses_to_record_unpersisted_bytes(
    db_session: Session, sample_rack_basic: Rack, fake_s3: FakeS3
) -> None:
    from main import app

    fake_s3.fail_writes = True
    client = _client(db_session)
    resp = client.post(
        f"/api/racks/{sample_rack_basic.id}/evidence/images",
        files=[("files", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"retention_days": "14", "consent_provider_processing": "false"},
    )
    app.dependency_overrides.clear()
    # The endpoint reports per-file outcomes; an unpersisted file is rejected, not recorded.
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["uploaded"] == []
    assert body["rejected"] == [{"filename": "a.jpg", "reason": storage.WRITE_FAILED}]
    assert db_session.query(ImageAssetRecord).count() == 0


def test_design_pack_survives_local_loss_and_still_downloads(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_s3: FakeS3
) -> None:
    user, bridge = _seed(db_session, tmp_path, monkeypatch)
    export = request_export(
        db_session,
        ExportRequest(
            request_id="req-durable",
            user_id=user.id,
            source_run_id=bridge.source_run_id,
            source_rig_revision_id=bridge.rig_revision_id,
            formats=("pdf", "json"),
            license="personal",
            credit_cost=3,
            idempotency_key="idem-durable-1",
            requested_at=NOW,
        ),
        artifact_manifest_hash=bridge.artifact_manifest_hash,
        export_version="1.0.0",
    )
    db_session.commit()
    assert fulfill_export(db_session, export.id).status == "succeeded"
    db_session.commit()
    assert any(
        k.startswith("store/design_packs/") or k.startswith("exports/design_packs/")
        for k in fake_s3.objects
    )

    shutil.rmtree(pack_dir_for_export(export.id))  # container restarted

    client = _client(db_session)
    token = client.post(
        f"/api/canon/exports/{export.id}/download-token",
        headers=_auth_headers(user),
        json={"ttl_seconds": 120},
    ).json()["token"]
    pdf = client.get(
        f"/api/canon/exports/{export.id}/artifacts/pdf",
        headers=_auth_headers(user),
        params={"token": token},
    )
    from main import app

    app.dependency_overrides.clear()
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")


def _upload_one(db_session: Session, rack: Rack) -> ImageAssetRecord:
    from main import app

    client = _client(db_session)
    resp = client.post(
        f"/api/racks/{rack.id}/evidence/images",
        files=[("files", ("a.jpg", _jpeg_bytes(), "image/jpeg"))],
        data={"retention_days": "1", "consent_provider_processing": "false"},
    )
    app.dependency_overrides.clear()
    assert resp.status_code == 201, resp.text
    return db_session.get(ImageAssetRecord, resp.json()["uploaded"][0]["id"])


def test_retention_retries_a_failed_durable_delete(
    db_session: Session, sample_rack_basic: Rack, fake_s3: FakeS3
) -> None:
    from datetime import datetime, timedelta, timezone

    from evidence.retention import expire_image_assets

    record = _upload_one(db_session, sample_rack_basic)
    record.retention_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()
    key = next(k for k in fake_s3.objects if k.startswith("exports/evidence/"))

    fake_s3.fail_deletes = 1
    first = expire_image_assets(db_session)
    db_session.commit()
    assert first == {"soft_deleted": 0, "purged_files": 0, "purge_deferred": 1}
    assert db_session.get(ImageAssetRecord, record.id).deleted_at is None
    assert key in fake_s3.objects

    second = expire_image_assets(db_session)
    db_session.commit()
    assert second == {"soft_deleted": 1, "purged_files": 1, "purge_deferred": 0}
    assert db_session.get(ImageAssetRecord, record.id).deleted_at is not None
    assert key not in fake_s3.objects
    assert fake_s3.delete_calls == 2


def test_delete_endpoint_reports_a_failed_purge_and_retries(
    db_session: Session, sample_rack_basic: Rack, fake_s3: FakeS3
) -> None:
    from main import app

    record = _upload_one(db_session, sample_rack_basic)
    key = next(k for k in fake_s3.objects if k.startswith("exports/evidence/"))
    url = f"/api/racks/{sample_rack_basic.id}/evidence/images/{record.id}"

    fake_s3.fail_deletes = 1
    client = _client(db_session)
    failed = client.delete(url, params={"purge_bytes": "true"})
    assert failed.status_code == 503
    assert failed.json()["detail"] == storage.WRITE_FAILED
    assert db_session.get(ImageAssetRecord, record.id).deleted_at is not None
    assert key in fake_s3.objects

    retried = client.delete(url, params={"purge_bytes": "true"})
    app.dependency_overrides.clear()
    assert retried.status_code == 200, retried.text
    assert key not in fake_s3.objects
