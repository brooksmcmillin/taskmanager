"""File storage service for handling uploads."""

import os
import uuid
from pathlib import Path

import aiofiles

from app.config import settings


class PathTraversalError(ValueError):
    """Raised when a path traversal attack is detected."""

    pass


class StorageService:
    """Service for managing file storage on the local filesystem."""

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize storage service with base path."""
        self.base_path = base_path or settings.upload_path

    def _ensure_base_dir(self) -> None:
        """Ensure the base upload directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, storage_path: str) -> Path:
        """Validate that the storage path stays within the base directory.

        Args:
            storage_path: The relative storage path to validate

        Returns:
            The resolved full path

        Raises:
            PathTraversalError: If the path attempts to escape the base directory
        """
        full_path = (self.base_path / storage_path).resolve()
        base_resolved = self.base_path.resolve()
        if not full_path.is_relative_to(base_resolved):
            raise PathTraversalError("Invalid storage path")
        return full_path

    async def save_file(
        self, content: bytes, filename: str, content_type: str
    ) -> tuple[str, int]:
        """
        Save file content to storage with a UUID-based path.

        Args:
            content: The file content as bytes
            filename: Original filename (used for extension)
            content_type: MIME type of the file

        Returns:
            Tuple of (storage_path, file_size)
        """
        # Ensure base directory exists
        self._ensure_base_dir()

        # Generate UUID-based path to prevent traversal attacks
        file_uuid = uuid.uuid4()
        extension = Path(filename).suffix.lower()
        storage_filename = f"{file_uuid}{extension}"

        # Create subdirectory based on first two chars of UUID for better distribution
        subdir = str(file_uuid)[:2]
        storage_dir = self.base_path / subdir
        os.makedirs(storage_dir, exist_ok=True)

        storage_path = f"{subdir}/{storage_filename}"
        full_path = self.base_path / storage_path

        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

        return storage_path, len(content)

    async def read_file(self, storage_path: str) -> bytes:
        """
        Read file content from storage.

        Args:
            storage_path: The relative storage path

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            PathTraversalError: If path attempts to escape base directory
        """
        full_path = self._validate_path(storage_path)
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            storage_path: The relative storage path

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            PathTraversalError: If path attempts to escape base directory
        """
        full_path = self._validate_path(storage_path)
        try:
            os.remove(full_path)
            return True
        except FileNotFoundError:
            return False

    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            storage_path: The relative storage path

        Returns:
            True if file exists

        Raises:
            PathTraversalError: If path attempts to escape base directory
        """
        full_path = self._validate_path(storage_path)
        return full_path.exists()


# Global instance
storage_service = StorageService()
