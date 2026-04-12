"""Knowledge base handlers for Desktop channel."""

import base64
import io
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.services.knowledge_engine import KnowledgeGraphEngine
from backend.services.knowledge_task_queue import KnowledgeTaskQueue


class _KnowledgeHandlerMixin:
    """Mixin providing common _send_error for knowledge handlers."""

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class KnowledgeListHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge directory listing requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            path = message.data.get("path", "knowledge/notes")
            items = self.engine.list_directory(path)
            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_LIST_RESULT,
                request_id=message.request_id,
                data={"path": path, "items": items}
            ))
        except Exception as e:
            logger.error(f"Failed to list knowledge directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list knowledge directory: {e}")


class KnowledgeReadHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge file read requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            path = message.data["path"]
            full_path = self.engine._resolve_path(path)
            if not full_path.exists():
                raise FileNotFoundError(f"Note not found: {path}")

            try:
                content = full_path.read_text(encoding="utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                content = full_path.read_bytes().hex()
                encoding = "hex"

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_READ_RESULT,
                request_id=message.request_id,
                data={"path": path, "content": content, "encoding": encoding}
            ))
        except Exception as e:
            logger.error(f"Failed to read knowledge note: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read knowledge note: {e}")


class KnowledgeWriteHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge file write requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            path = message.data["path"]
            content = message.data["content"]
            self.engine.write_note(path, content)

            # 关键：如果写入 knowledge 目录的 markdown，立即更新索引
            if path.startswith("knowledge/") and path.endswith(".md"):
                self.engine.update_note(path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_WRITE_RESULT,
                request_id=message.request_id,
                data={"path": path, "success": True}
            ))
        except Exception as e:
            logger.error(f"Failed to write knowledge note: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to write knowledge note: {e}")


class KnowledgeDeleteHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge file delete requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            path = message.data["path"]
            full_path = self.engine.workspace_root / path

            # Security check: ensure path is within workspace
            workspace_root = Path(self.engine.workspace_root).resolve()
            resolved_full = full_path.resolve()
            if not str(resolved_full).startswith(str(workspace_root)):
                await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                return

            if full_path.exists():
                if full_path.is_dir():
                    shutil.rmtree(full_path)
                else:
                    full_path.unlink()
            if path.endswith(".md"):
                self.engine.db.execute("DELETE FROM knowledge_nodes WHERE path = ?", (path,))
                self.engine.db.commit()
                self.engine._invalidate_cache()

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_DELETE_RESULT,
                request_id=message.request_id,
                data={"path": path, "success": True}
            ))
        except Exception as e:
            logger.error(f"Failed to delete knowledge note: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete knowledge note: {e}")


class KnowledgeSearchHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge search requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            query = message.data.get("query", "")
            results = self.engine.search_notes(query)
            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_SEARCH_RESULT,
                request_id=message.request_id,
                data={"query": query, "results": results}
            ))
        except Exception as e:
            logger.error(f"Failed to search knowledge notes: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to search knowledge notes: {e}")


class KnowledgeGraphHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge graph visualization requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            center = message.data.get("center")
            depth = message.data.get("depth", 1)
            limit = message.data.get("limit", 200)
            tag_filter = message.data.get("tag")
            graph = self.engine.get_graph(center_path=center, depth=depth, limit=limit, tag_filter=tag_filter)
            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_GRAPH_RESULT,
                request_id=message.request_id,
                data=graph
            ))
        except Exception as e:
            logger.error(f"Failed to get knowledge graph: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get knowledge graph: {e}")


class KnowledgeDistillListHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge distillation task list requests with pagination."""

    def __init__(self, bus, queue: KnowledgeTaskQueue):
        super().__init__(bus)
        self.queue = queue

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            limit = message.data.get("limit", 20)
            offset = message.data.get("offset", 0)
            tasks, total = self.queue.list_tasks(limit=limit, offset=offset)
            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_DISTILL_LIST_RESULT,
                request_id=message.request_id,
                data={
                    "tasks": [
                        {
                            "id": t.id,
                            "request_id": t.request_id,
                            "source_path": t.source_path,
                            "status": t.status,
                            "stage": t.stage,
                            "message": t.message,
                            "progress": t.progress,
                            "result_path": t.result_path,
                            "error": t.error,
                            "created_at": t.created_at,
                            "updated_at": t.updated_at,
                        }
                        for t in tasks
                    ],
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }
                }
            ))
        except Exception as e:
            logger.error(f"Failed to list distill tasks: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list distill tasks: {e}")


class KnowledgeDistillHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge distillation requests (async queue mode).

    This handler uses the task queue for asynchronous execution,
    writing the distilled content to a markdown file.
    """

    def __init__(self, bus, queue: KnowledgeTaskQueue):
        super().__init__(bus)
        self.queue = queue

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            from backend.utils.helpers import get_workspace_path

            source_path = message.data["source_path"]
            prompt = message.data.get("prompt", "")
            template = message.data.get("template", "custom")
            # Use frontend-provided task_id for progress tracking
            task_id = message.data.get("task_id") or message.request_id

            # Determine output_path
            # - If provided, use it (write to file)
            # - If not provided, auto-generate (write to file)
            output_path = message.data.get("output_path")
            if not output_path:
                output_path = f"knowledge/notes/{Path(source_path).stem}_extracted.md"

            # Enqueue task for async execution
            job_id = self.queue.enqueue(
                request_id=task_id,
                source_path=source_path,
                prompt=prompt,
                output_path=output_path,
                template=template,
            )

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_DISTILL_RESULT,
                request_id=message.request_id,
                data={
                    "job_id": job_id,
                    "status": "queued",
                    "message": "Task queued. Progress will be pushed via knowledge_distill_progress events.",
                    "output_path": output_path,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to queue distillation: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to queue distillation: {e}")


class KnowledgeDistillDetailHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge distill task detail requests with iterations."""

    def __init__(self, bus, queue: KnowledgeTaskQueue):
        super().__init__(bus)
        self.queue = queue

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            task_id = message.data.get("task_id")
            if not task_id:
                await self._send_error(websocket, message.request_id, "task_id is required")
                return

            task = self.queue.get_task_with_iterations(task_id)
            if not task:
                await self._send_error(websocket, message.request_id, f"Task {task_id} not found")
                return

            # Build result in SubagentSyncFold compatible format
            iterations = task.get("iterations", [])
            total_prompt_tokens = sum(
                (json.loads(it.get("token_usage") or "{}")).get("prompt_tokens", 0)
                for it in iterations
            )
            total_completion_tokens = sum(
                (json.loads(it.get("token_usage") or "{}")).get("completion_tokens", 0)
                for it in iterations
            )
            # Calculate duration from task created_at and updated_at
            try:
                from datetime import datetime
                created_at = datetime.fromisoformat(task["created_at"])
                updated_at = datetime.fromisoformat(task["updated_at"])
                total_duration = (updated_at - created_at).total_seconds()
            except Exception:
                total_duration = 0

            # Extract actual markdown from the last iteration's reasoning (not the prompt)
            summary = ""
            for i in range(len(iterations) - 1, -1, -1):
                reasoning = iterations[i].get("reasoning", "")
                if reasoning and reasoning.strip():
                    summary = reasoning.strip()
                    break

            # Also extract markdown from iterations[-1] tools results if summary is still empty
            if not summary and iterations:
                for tool_result in iterations[-1].get("tools", []):
                    result_str = tool_result.get("result", "")
                    if result_str and ("---" in result_str or "# " in result_str):
                        summary = result_str
                        break

            result = {
                "status": task["status"],
                "label": f"Distill: {task['source_path'].split('/')[-1]}",
                "summary": summary or task.get("prompt", ""),
                "output_path": task.get("result_path"),
                "token_usage": {
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                },
                "duration": total_duration,
                "iterations": iterations,
            }

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_DISTILL_DETAIL_RESULT,
                request_id=message.request_id,
                data={"task": task, "result": result}
            ))
        except Exception as e:
            logger.error(f"Failed to get distill task detail: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get distill task detail: {e}")


class KnowledgeGetTagsHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle get all tags request."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            tags = self.engine.get_tags()
            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_GET_TAGS_RESULT,
                request_id=message.request_id,
                data={"tags": tags}
            ))
        except Exception as e:
            logger.error(f"Failed to get tags: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get tags: {e}")


class KnowledgeExportHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge base export requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine, queue: KnowledgeTaskQueue | None = None):
        super().__init__(bus)
        self.engine = engine
        self.queue = queue

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            workspace = Path(self.engine.workspace_root)
            knowledge_dir = workspace / "knowledge"
            notes_dir = knowledge_dir / "notes"
            raw_dir = knowledge_dir / "raw"
            index_db = knowledge_dir / ".knowledge_index.db"
            tasks_db = knowledge_dir / ".distill_tasks.db"

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                # manifest
                manifest = {
                    "version": "1.0",
                    "exported_at": datetime.now().isoformat(),
                    "workspace": str(workspace),
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))

                # notes
                if notes_dir.exists():
                    for fp in notes_dir.rglob("*"):
                        if fp.is_file():
                            arcname = str(fp.relative_to(workspace))
                            zf.write(fp, arcname)

                # raw attachments
                if raw_dir.exists():
                    for fp in raw_dir.rglob("*"):
                        if fp.is_file():
                            arcname = str(fp.relative_to(workspace))
                            zf.write(fp, arcname)

                # databases
                if index_db.exists():
                    zf.write(index_db, str(index_db.relative_to(workspace)))
                if tasks_db.exists():
                    zf.write(tasks_db, str(tasks_db.relative_to(workspace)))

            buffer.seek(0)
            b64_data = base64.b64encode(buffer.read()).decode("utf-8")
            filename = f"knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_EXPORT_RESULT,
                request_id=message.request_id,
                data={"filename": filename, "data": b64_data}
            ))
        except Exception as e:
            logger.error(f"Failed to export knowledge base: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to export knowledge base: {e}")


class KnowledgeImportHandler(_KnowledgeHandlerMixin, MessageHandler):
    """Handle knowledge base import requests."""

    def __init__(self, bus, engine: KnowledgeGraphEngine):
        super().__init__(bus)
        self.engine = engine

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            zip_path_rel = message.data.get("zip_path")
            if not zip_path_rel:
                await self._send_error(websocket, message.request_id, "zip_path is required")
                return

            workspace = Path(self.engine.workspace_root)
            zip_path = workspace / zip_path_rel
            if not zip_path.exists():
                await self._send_error(websocket, message.request_id, f"Zip file not found: {zip_path_rel}")
                return

            # Security check
            resolved_zip = zip_path.resolve()
            resolved_workspace = workspace.resolve()
            if not str(resolved_zip).startswith(str(resolved_workspace)):
                await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                return

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Validate manifest
                manifest_bytes = zf.read("manifest.json")
                manifest = json.loads(manifest_bytes)
                if manifest.get("version") != "1.0":
                    await self._send_error(websocket, message.request_id, "Unsupported export version")
                    return

                for member in zf.namelist():
                    if member.endswith("/"):
                        continue
                    # Prevent directory traversal
                    target = workspace / member
                    if not str(target.resolve()).startswith(str(resolved_workspace)):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())

            # Reindex all markdown notes
            notes_dir = workspace / "knowledge" / "notes"
            if notes_dir.exists():
                for fp in notes_dir.rglob("*.md"):
                    rel = str(fp.relative_to(workspace))
                    self.engine.update_note(rel)

            self.engine._invalidate_cache()

            await self.send_response(websocket, WSMessage(
                type=MessageType.KNOWLEDGE_IMPORT_RESULT,
                request_id=message.request_id,
                data={"success": True}
            ))
        except Exception as e:
            logger.error(f"Failed to import knowledge base: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to import knowledge base: {e}")
