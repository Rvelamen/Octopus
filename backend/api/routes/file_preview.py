"""File preview conversion API (PPTX -> PDF via LibreOffice)."""

import hashlib
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

router = APIRouter(prefix="/api/file-preview")


def _get_workspace_root() -> Path:
    from backend.utils.helpers import get_workspace_path
    return Path(get_workspace_path())


def _convert_with_soffice(input_path: Path, output_dir: Path) -> Path:
    """Convert a file to PDF using LibreOffice headless mode."""
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pdf:impress_pdf_Export:ExportNotesPages=false",
        "--outdir", str(output_dir),
        str(input_path),
    ]
    logger.info(f"Converting {input_path} to PDF via LibreOffice")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"LibreOffice conversion failed: {result.stderr}")
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice conversion timed out (> 120s)")

    # Output file has same base name with .pdf extension
    output_path = output_dir / (input_path.stem + ".pdf")
    if not output_path.exists():
        # Sometimes LibreOffice names differently; search for any PDF in output_dir
        pdfs = list(output_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError("PDF output not found after conversion")
        output_path = pdfs[0]
    return output_path


@router.get("/pdf")
async def get_pdf_preview(path: str = Query(..., description="Relative path to the file")):
    """Return a PDF version of the given file (currently supports PPTX/PPT via LibreOffice)."""
    workspace_root = _get_workspace_root()
    full_path = workspace_root / path

    # Security check
    try:
        full_path = full_path.resolve()
        workspace_root = workspace_root.resolve()
        if not str(full_path).startswith(str(workspace_root)):
            raise HTTPException(status_code=403, detail="Access denied: path outside workspace")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    ext = full_path.suffix.lower()
    if ext not in {".pptx", ".ppt", ".pptm", ".ppsx", ".ppsm", ".potx", ".potm", ".thmx", ".docx", ".doc", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type for PDF preview: {ext}")

    # Cache directory inside workspace
    cache_dir = workspace_root / ".cache" / "pdf_preview"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Use a cache key based on file path + mtime + size to invalidate when file changes
    stat = full_path.stat()
    cache_key = hashlib.md5(f"{full_path}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()
    cached_pdf = cache_dir / f"{cache_key}.pdf"

    if not cached_pdf.exists():
        # Use a temp sub-dir per conversion to avoid name collisions
        tmp_dir = cache_dir / cache_key
        tmp_dir.mkdir(parents=True, exist_ok=True)
        output_pdf = _convert_with_soffice(full_path, tmp_dir)
        output_pdf.rename(cached_pdf)
        # Cleanup tmp dir
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

    pdf_bytes = cached_pdf.read_bytes()
    import base64
    return {
        "success": True,
        "encoding": "base64",
        "content": base64.b64encode(pdf_bytes).decode("ascii"),
        "size": len(pdf_bytes),
    }
