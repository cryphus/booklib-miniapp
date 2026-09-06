from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import (
    ALLOWED_IMAGE_MIME,
    StorageService,
    StoredFile,
    sniff_image_mime,
)
from app.services.storage.local import LocalStorageService


@lru_cache
def get_storage() -> StorageService:
    if settings.STORAGE_BACKEND == "local":
        return LocalStorageService()
    # TODO(storage): add an S3/R2/MinIO backend implementing the same StorageService interface.
    raise NotImplementedError(f"Storage backend '{settings.STORAGE_BACKEND}' is not implemented")


__all__ = [
    "StorageService",
    "StoredFile",
    "LocalStorageService",
    "get_storage",
    "sniff_image_mime",
    "ALLOWED_IMAGE_MIME",
]
