"""REST API for Library PDF upload via HTTP (faster than WebSocket hex)."""

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from loguru import logger

from backend.utils.helpers import get_workspace_path

router = APIRouter(prefix="/api/library")


@router.post("/upload")
async def library_upload(file: UploadFile = File(...)):
    """
    Upload a PDF file directly via HTTP multipart/form-data.
    Returns a temp path relative to workspace for subsequent library_create WS call.
    """
    try:
        workspace = get_workspace_path()
        uploads_dir = workspace / "knowledge" / "library" / "_uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        original_name = file.filename or "upload.pdf"
        safe_name = Path(original_name).name
        temp_name = f"_tmp_{uuid.uuid4().hex[:8]}_{safe_name}"
        dest = uploads_dir / temp_name

        # Run sync file copy in executor to avoid blocking the event loop
        # for large PDFs (which can break WebSocket keepalive)
        loop = asyncio.get_running_loop()

        def _save():
            with open(dest, "wb") as f:
                shutil.copyfileobj(file.file, f)

        await loop.run_in_executor(None, _save)

        rel_path = str(dest.relative_to(workspace))
        logger.info(f"[library_upload] Saved upload to {rel_path} ({dest.stat().st_size} bytes)")
        return {"success": True, "temp_path": rel_path}
    except Exception as e:
        logger.error(f"[library_upload] Failed: {e}")
        return {"success": False, "error": str(e)}
