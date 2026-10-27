"""Durable storage for files the backend records by local path (spec 006 T055).

Evidence uploads, PatchBook exports and design packs are written under ``export_dir`` /
``export_store_root`` and their local paths are stored in Postgres. With
``STORAGE_BACKEND=s3`` every durable write is mirrored to an S3-compatible bucket
(Cloudflare R2), and a missing local file is restored from the bucket before it is read.
The local disk is then only a cache: a Cloudflare Container's disk is wiped when the
instance sleeps, restarts or redeploys.

Object keys are the file's path relative to its storage root, prefixed by the root's
label, so existing ``storage_path`` values keep working and no schema change is needed.
"""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from core.config import settings

PATH_OUTSIDE_ROOTS = "STORAGE_PATH_OUTSIDE_ROOTS"
NOT_CONFIGURED = "STORAGE_NOT_CONFIGURED"
WRITE_FAILED = "STORAGE_WRITE_FAILED"
READ_FAILED = "STORAGE_READ_FAILED"


class StorageError(RuntimeError):
    """A durable-storage operation failed; ``code`` is stable for API errors."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class FileStore(Protocol):
    def persist(self, path: Path) -> None: ...

    def ensure_local(self, path: Path) -> bool: ...

    def delete(self, path: Path) -> bool: ...

    def persist_tree(self, directory: Path) -> None: ...

    def ensure_local_tree(self, directory: Path) -> bool: ...


class LocalFileStore:
    """The local disk is the store. Matches the behavior before T055."""

    def persist(self, path: Path) -> None:
        return None

    def ensure_local(self, path: Path) -> bool:
        return Path(path).exists()

    def delete(self, path: Path) -> bool:
        try:
            Path(path).unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def persist_tree(self, directory: Path) -> None:
        return None

    def ensure_local_tree(self, directory: Path) -> bool:
        return Path(directory).exists()


class S3FileStore:
    """Mirror files under labelled local roots into one S3-compatible bucket."""

    def __init__(self, client: Any, bucket: str, roots: dict[str, Path], prefix: str = ""):
        self._client = client
        self._bucket = bucket
        # Longest root first so a nested root wins over its parent.
        self._roots = sorted(
            ((label, Path(root).resolve()) for label, root in roots.items()),
            key=lambda item: len(item[1].parts),
            reverse=True,
        )
        self._prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""

    def key_for(self, path: Path) -> str:
        resolved = Path(path).resolve()
        for label, root in self._roots:
            if resolved == root or resolved.is_relative_to(root):
                rel = resolved.relative_to(root).as_posix()
                return f"{self._prefix}{label}/{rel}".rstrip("/")
        raise StorageError(PATH_OUTSIDE_ROOTS, str(path))

    def persist(self, path: Path) -> None:
        key = self.key_for(path)
        try:
            data = Path(path).read_bytes()
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        except StorageError:
            raise
        except Exception as exc:  # botocore raises several unrelated types
            raise StorageError(WRITE_FAILED, f"{key}: {type(exc).__name__}") from exc

    def ensure_local(self, path: Path) -> bool:
        path = Path(path)
        if path.exists():
            return True
        key = self.key_for(path)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            data = response["Body"].read()
        except Exception as exc:
            if _is_missing(exc):
                return False
            raise StorageError(READ_FAILED, f"{key}: {type(exc).__name__}") from exc
        _write_atomic(path, data)
        return True

    def delete(self, path: Path) -> bool:
        # Remove the cached copy, then the durable one. S3 deletes succeed whether or
        # not the object exists, so a successful call means the bytes are gone.
        LocalFileStore().delete(path)
        key = self.key_for(path)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise StorageError(WRITE_FAILED, f"{key}: {type(exc).__name__}") from exc
        return True

    def persist_tree(self, directory: Path) -> None:
        for file in sorted(Path(directory).rglob("*")):
            if file.is_file():
                self.persist(file)

    def ensure_local_tree(self, directory: Path) -> bool:
        directory = Path(directory)
        prefix = self.key_for(directory) + "/"
        found = False
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            try:
                page = self._client.list_objects_v2(**kwargs)
            except Exception as exc:
                raise StorageError(READ_FAILED, f"{prefix}: {type(exc).__name__}") from exc
            for item in page.get("Contents", []) or []:
                found = True
                rel = str(item["Key"])[len(prefix) :]
                if rel:
                    self.ensure_local(directory / rel)
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
        return found or directory.exists()


def _is_missing(exc: Exception) -> bool:
    code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
    return code in {"NoSuchKey", "404", "NotFound"}


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".restore-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


@lru_cache(maxsize=4)
def _s3_client(endpoint_url: str, region: str, access_key_id: str, secret_access_key: str) -> Any:
    import boto3  # imported lazily: the local backend never needs it

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


def get_file_store() -> FileStore:
    """Return the configured store. Raises StorageError if S3 is selected but incomplete."""

    backend = (settings.storage_backend or "local").strip().lower()
    if backend == "local":
        return LocalFileStore()
    if backend != "s3":
        raise StorageError(NOT_CONFIGURED, f"unknown STORAGE_BACKEND {backend!r}")
    required = {
        "S3_ENDPOINT_URL": settings.s3_endpoint_url,
        "S3_BUCKET": settings.s3_bucket,
        "S3_ACCESS_KEY_ID": settings.s3_access_key_id,
        "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
    }
    missing = sorted(name for name, value in required.items() if not value)
    if missing:
        raise StorageError(NOT_CONFIGURED, "missing " + ", ".join(missing))
    client = _s3_client(
        settings.s3_endpoint_url,
        settings.s3_region or "auto",
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
    )
    roots = {"exports": Path(settings.export_dir)}
    if settings.export_store_root:
        roots["store"] = Path(settings.export_store_root)
    return S3FileStore(client, settings.s3_bucket, roots, prefix=settings.s3_key_prefix)
