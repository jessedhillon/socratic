"""Object storage abstraction for file uploads (videos, etc.)."""

from .store import LocalObjectStore, ObjectStore, UploadResult

__all__ = ["LocalObjectStore", "ObjectStore", "UploadResult"]
