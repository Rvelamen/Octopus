"""File preview conversion handler for Desktop channel."""

import base64
import hashlib
import shutil
import subprocess
from pathlib import Path

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage


def _get_soffice_path() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


class FilePreviewPDFHandler(MessageHandler):
    """Handle file-to-PDF preview conversion requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        path = message.data.get("path", "")
        await self._process(websocket, message, path)

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated) -> None:
        await self._process(websocket, message, validated.path)

    async def _process(self, websocket: WebSocket, message: WSMessage, path: str) -> None:
        soffice = _get_soffice_path()
        if not soffice:
            await self._send_error(
                websocket, message.request_id,
                "LibreOffice not found. Please install LibreOffice to preview PowerPoint/Word/Excel files, or download the file directly."
            )
            return

        from backend.utils.helpers import get_workspace_path

        workspace_root = Path(get_workspace_path())
        full_path = workspace_root / path

        # Security check
        try:
            full_path = full_path.resolve()
            workspace_root = workspace_root.resolve()
            if not str(full_path).startswith(str(workspace_root)):
                await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                return
        except Exception:
            await self._send_error(websocket, message.request_id, "Invalid path")
            return

        if not full_path.exists():
            await self._send_error(websocket, message.request_id, "File not found")
            return
        if not full_path.is_file():
            await self._send_error(websocket, message.request_id, "Path is not a file")
            return

        ext = full_path.suffix.lower()
        if ext not in {".pptx", ".ppt", ".pptm", ".ppsx", ".ppsm", ".potx", ".potm", ".thmx", ".docx", ".doc", ".xlsx", ".xls"}:
            await self._send_error(websocket, message.request_id, f"Unsupported file type for PDF preview: {ext}")
            return

        # Cache directory inside workspace
        cache_dir = workspace_root / ".cache" / "pdf_preview"
        cache_dir.mkdir(parents=True, exist_ok=True)

        stat = full_path.stat()
        cache_key = hashlib.md5(f"{full_path}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()
        cached_pdf = cache_dir / f"{cache_key}.pdf"

        if not cached_pdf.exists():
            tmp_dir = cache_dir / cache_key
            tmp_dir.mkdir(parents=True, exist_ok=True)
            try:
                output_pdf = self._convert_with_soffice(full_path, tmp_dir)
                output_pdf.rename(cached_pdf)
            except Exception as e:
                logger.error(f"PDF conversion failed: {e}")
                await self._send_error(websocket, message.request_id, f"PDF conversion failed: {e}")
                return
            finally:
                try:
                    tmp_dir.rmdir()
                except Exception:
                    pass

        try:
            pdf_bytes = cached_pdf.read_bytes()
            await self.send_response(websocket, WSMessage(
                type=MessageType.FILE_PREVIEW_PDF_RESULT,
                request_id=message.request_id,
                data={
                    "success": True,
                    "encoding": "base64",
                    "content": base64.b64encode(pdf_bytes).decode("ascii"),
                    "size": len(pdf_bytes),
                }
            ))
        except Exception as e:
            logger.error(f"Failed to read cached PDF: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read PDF: {e}")

    def _convert_with_soffice(self, input_path: Path, output_dir: Path) -> Path:
        soffice = _get_soffice_path()
        if not soffice:
            raise RuntimeError("LibreOffice not found")
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf:impress_pdf_Export:ExportNotesPages=false",
            "--outdir", str(output_dir),
            str(input_path),
        ]
        logger.info(f"Converting {input_path} to PDF via LibreOffice")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")
        output_path = output_dir / (input_path.stem + ".pdf")
        if not output_path.exists():
            pdfs = list(output_dir.glob("*.pdf"))
            if not pdfs:
                raise RuntimeError("PDF output not found after conversion")
            output_path = pdfs[0]
        return output_path

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
