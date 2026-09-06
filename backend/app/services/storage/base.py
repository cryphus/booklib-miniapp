from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

ALLOWED_IMAGE_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# (offset, signature, mime)
_MAGIC = [
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
]


def sniff_image_mime(data: bytes) -> str | None:
    """Content-based check. The client-supplied Content-Type is never trusted alone."""
    for offset, signature, mime in _MAGIC:
        if data[offset : offset + len(signature)] == signature:
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@dataclass
class StoredFile:
    key: str
    url: str
    size: int
    content_type: str


class StorageService(ABC):
    """Business logic only ever sees this interface, so S3/R2/MinIO can be dropped in later."""

    @abstractmethod
    async def save(self, data: bytes, *, content_type: str, prefix: str = "") -> StoredFile: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...
