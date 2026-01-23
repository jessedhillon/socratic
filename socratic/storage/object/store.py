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


class ChunkUploadResult(p.BaseModel):
    """Result of a chunk upload operation."""

    model_config = p.ConfigDict(frozen=True)

    # Sequence number of the chunk
    sequence: int

    # Size of this chunk in bytes
    size: int

    # Total number of chunks uploaded so far
    total_chunks: int


class FinalizeResult(p.BaseModel):
    """Result of finalizing a chunked upload."""

    model_config = p.ConfigDict(frozen=True)

    # The URL to access the assembled file
    url: str

    # Total size of the assembled file in bytes
    total_size: int

    # Number of chunks that were assembled
    chunks_assembled: int

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

    @abc.abstractmethod
    async def upload_chunk(
        self,
        key_prefix: str,
        sequence: int,
        file: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> ChunkUploadResult:
        """Upload a chunk of a multi-part upload.

        Args:
            key_prefix: The prefix for chunk storage (e.g., "assessments/{attempt_id}/video").
            sequence: The sequence number of this chunk (0-indexed).
            file: A file-like object containing the chunk data.
            content_type: MIME type of the final assembled file.

        Returns:
            ChunkUploadResult with the sequence and chunk count.
        """
        ...

    @abc.abstractmethod
    async def get_chunk_count(self, key_prefix: str) -> int:
        """Get the number of chunks uploaded for a key prefix.

        Args:
            key_prefix: The prefix used for chunk storage.

        Returns:
            Number of chunks uploaded.
        """
        ...

    @abc.abstractmethod
    async def finalize_chunks(
        self,
        key_prefix: str,
        final_key: str,
        content_type: str = "application/octet-stream",
    ) -> FinalizeResult:
        """Assemble uploaded chunks into a final file.

        Args:
            key_prefix: The prefix used for chunk storage.
            final_key: The key for the final assembled file.
            content_type: MIME type of the final file.

        Returns:
            FinalizeResult with the URL and metadata of the assembled file.
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

    async def upload_chunk(
        self,
        key_prefix: str,
        sequence: int,
        file: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> ChunkUploadResult:
        """Upload a chunk to local filesystem."""
        chunks_dir = self._base_path / f"{key_prefix}.chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        chunk_path = chunks_dir / f"{sequence:06d}.chunk"

        # Stream copy the chunk
        with open(chunk_path, "wb") as dest:
            shutil.copyfileobj(file, dest)

        chunk_size = chunk_path.stat().st_size

        # Count total chunks in directory
        total_chunks = len(list(chunks_dir.glob("*.chunk")))

        return ChunkUploadResult(
            sequence=sequence,
            size=chunk_size,
            total_chunks=total_chunks,
        )

    async def get_chunk_count(self, key_prefix: str) -> int:
        """Get the number of chunks uploaded for a key prefix."""
        chunks_dir = self._base_path / f"{key_prefix}.chunks"

        if not chunks_dir.exists():
            return 0

        return len(list(chunks_dir.glob("*.chunk")))

    async def finalize_chunks(
        self,
        key_prefix: str,
        final_key: str,
        content_type: str = "application/octet-stream",
    ) -> FinalizeResult:
        """Assemble uploaded chunks into a final file."""
        chunks_dir = self._base_path / f"{key_prefix}.chunks"
        final_path = self._base_path / final_key

        # Ensure parent directories exist
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Get sorted chunk files
        chunk_files = sorted(chunks_dir.glob("*.chunk"))

        if not chunk_files:
            raise ValueError(f"No chunks found for key_prefix: {key_prefix}")

        # Assemble chunks into final file
        total_size = 0
        with open(final_path, "wb") as dest:
            for chunk_file in chunk_files:
                with open(chunk_file, "rb") as src:
                    shutil.copyfileobj(src, dest)
                total_size += chunk_file.stat().st_size

        chunks_assembled = len(chunk_files)

        # Clean up chunks directory
        for chunk_file in chunk_files:
            chunk_file.unlink()
        chunks_dir.rmdir()

        return FinalizeResult(
            url=self.get_url(final_key),
            total_size=total_size,
            chunks_assembled=chunks_assembled,
            content_type=content_type,
        )
