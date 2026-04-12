"""Simple in-process chunked upload assembler."""

import hashlib
import os
from pathlib import Path
from typing import Optional

from loguru import logger


class ChunkedUploadManager:
    """Manages temporary chunk files and final assembly."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.temp_dir = self.workspace_root / ".upload_chunks"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _chunk_path(self, upload_id: str, chunk_index: int) -> Path:
        upload_dir = self.temp_dir / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir / f"{chunk_index}"

    def write_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        total_chunks: int,
        data: bytes,
    ) -> int:
        """Write a single chunk to temp storage. Returns total received chunks."""
        chunk_file = self._chunk_path(upload_id, chunk_index)
        chunk_file.write_bytes(data)
        upload_dir = chunk_file.parent
        return sum(1 for f in upload_dir.iterdir() if f.is_file())

    def assemble_if_complete(
        self,
        upload_id: str,
        total_chunks: int,
        target_path: str,
        expected_md5: Optional[str] = None,
    ) -> bool:
        """If all chunks are present, assemble them into target_path.

        Returns True if assembly happened (or already existed).
        """
        upload_dir = self.temp_dir / upload_id
        if not upload_dir.exists():
            return False

        received = sum(1 for f in upload_dir.iterdir() if f.is_file())
        if received < total_chunks:
            return False

        # Assemble
        target = self.workspace_root / target_path
        target.parent.mkdir(parents=True, exist_ok=True)

        with target.open("wb") as out:
            for i in range(total_chunks):
                chunk_file = upload_dir / str(i)
                out.write(chunk_file.read_bytes())

        # Optional md5 verification
        if expected_md5:
            actual_md5 = hashlib.md5(target.read_bytes()).hexdigest()
            if actual_md5 != expected_md5:
                target.unlink(missing_ok=True)
                _cleanup_dir(upload_dir)
                raise ValueError(f"MD5 mismatch: expected {expected_md5}, got {actual_md5}")

        # Cleanup temp chunks
        _cleanup_dir(upload_dir)
        logger.info(f"Assembled chunked upload {upload_id} -> {target_path}")
        return True

    def cancel(self, upload_id: str) -> None:
        upload_dir = self.temp_dir / upload_id
        _cleanup_dir(upload_dir)


def _cleanup_dir(directory: Path) -> None:
    if not directory.exists():
        return
    for f in directory.iterdir():
        if f.is_file():
            f.unlink()
    directory.rmdir()
