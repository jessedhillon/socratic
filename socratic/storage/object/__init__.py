"""Object storage abstraction for file uploads (videos, etc.)."""

from .store import ObjectStore, UploadResult

__all__ = ["ObjectStore", "UploadResult"]
