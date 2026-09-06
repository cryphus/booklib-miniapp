from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.errors import ValidationError
from app.services.storage.base import ALLOWED_IMAGE_MIME, StoredFile, StorageService


class LocalStorageService(StorageService):
    """Files on a Docker volume. Same interface an S3 backend will implement."""

    def __init__(self, root: str | None = None, public_base_url: str | None = None) -> None:
        self.root = Path(root or settings.STORAGE_LOCAL_DIR)
        self.public_base_url = (public_base_url or settings.STORAGE_PUBLIC_BASE_URL).rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, data: bytes, *, content_type: str, prefix: str = "") -> StoredFile:
        extension = ALLOWED_IMAGE_MIME.get(content_type)
        if extension is None:
            raise ValidationError(f"Unsupported file type: {content_type}", code="UNSUPPORTED_MEDIA_TYPE")
        if len(data) > settings.UPLOAD_MAX_BYTES:
            raise ValidationError("File is too large", code="FILE_TOO_LARGE")

        key = f"{prefix.strip('/') + '/' if prefix else ''}{uuid.uuid4().hex}{extension}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return StoredFile(key=key, url=self.url_for(key), size=len(data), content_type=content_type)

    async def delete(self, key: str) -> None:
        # Guard against traversal in a stored key.
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            return
        if path.exists():
            await asyncio.to_thread(path.unlink)

    def url_for(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"
