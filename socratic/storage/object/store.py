"""Object storage interface and implementations."""

from __future__ import annotations

import abc
import shutil
import typing as t
from pathlib import Path

import pydantic as p

if t.TYPE_CHECKING:
    from typing import BinaryIO


class UploadResult(p.BaseModel):
    """Result of an upload operation."""

    model_config = p.ConfigDict(frozen=True)

    # The URL to access the uploaded file
    url: str

    # Size of the uploaded file in bytes
    size: int

    # Content type of the file
    content_type: str


class ObjectStore(abc.ABC):
    """Abstract base class for object storage."""

    @abc.abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """Upload data to storage.

        Args:
            key: The storage key (path/filename) for the object.
            data: The file contents as bytes.
            content_type: MIME type of the file.

        Returns:
            UploadResult with the URL and metadata.
        """
        ...

    @abc.abstractmethod
    async def upload_stream(
        self,
        key: str,
        file: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """Upload from a file-like object to storage (streaming, memory-efficient).

        Args:
            key: The storage key (path/filename) for the object.
            file: A file-like object to read from.
            content_type: MIME type of the file.

        Returns:
            UploadResult with the URL and metadata.
        """
        ...

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an object from storage.

        Args:
            key: The storage key to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    @abc.abstractmethod
    def get_url(self, key: str) -> str:
        """Get the URL for an object.

        Args:
            key: The storage key.

        Returns:
            URL to access the object.
        """
        ...


class LocalObjectStore(ObjectStore):
    """Local filesystem implementation for development."""

    def __init__(self, base_path: Path, url_prefix: str = "/uploads") -> None:
        """Initialize local object store.

        Args:
            base_path: Directory to store files in.
            url_prefix: URL prefix for accessing files (served by web server).
        """
        self._base_path = base_path
        self._url_prefix = url_prefix.rstrip("/")

        # Ensure base directory exists
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """Upload data to local filesystem."""
        file_path = self._base_path / key

        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_bytes(data)

        return UploadResult(
            url=self.get_url(key),
            size=len(data),
            content_type=content_type,
        )

    async def upload_stream(
        self,
        key: str,
        file: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """Upload from file-like object to local filesystem (streaming)."""
        file_path = self._base_path / key

        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Stream copy in chunks (default 64KB chunks)
        with open(file_path, "wb") as dest:
            shutil.copyfileobj(file, dest)

        # Get final size
        size = file_path.stat().st_size

        return UploadResult(
            url=self.get_url(key),
            size=size,
            content_type=content_type,
        )

    async def delete(self, key: str) -> bool:
        """Delete file from local filesystem."""
        file_path = self._base_path / key

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    def get_url(self, key: str) -> str:
        """Get URL for local file (served by web server)."""
        return f"{self._url_prefix}/{key}"
