"""Workspace handlers for Desktop channel."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.schemas import (
    WorkspaceGetRootRequest,
    WorkspaceListRequest,
    WorkspaceReadRequest,
    WorkspaceWriteRequest,
    WorkspaceWriteChunkRequest,
    WorkspaceDeleteRequest,
    WorkspaceMkdirRequest,
    WorkspaceRenameRequest,
)
from backend.data import Database, SessionRepository
from backend.services.chunked_upload import ChunkedUploadManager


class WorkspaceGetRootHandler(MessageHandler):
    """Handle get workspace root path requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return the workspace root path."""
        try:
            # Get workspace path from helpers
            from backend.utils.helpers import get_workspace_path
            workspace_root = str(get_workspace_path())

            # Ensure workspace directory exists
            Path(workspace_root).mkdir(parents=True, exist_ok=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_ROOT,
                request_id=message.request_id,
                data={"root": workspace_root}
            ))
        except Exception as e:
            logger.error(f"Failed to get workspace root: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get workspace root: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceGetRootRequest) -> None:
        """Return the workspace root path."""
        try:
            # Get workspace path from helpers
            from backend.utils.helpers import get_workspace_path
            workspace_root = str(get_workspace_path())

            # Ensure workspace directory exists
            Path(workspace_root).mkdir(parents=True, exist_ok=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_ROOT,
                request_id=message.request_id,
                data={"root": workspace_root}
            ))
        except Exception as e:
            logger.error(f"Failed to get workspace root: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to get workspace root: {e}")

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceListHandler(MessageHandler):
    """Handle list directory contents requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return directory listing."""
        try:
            path = message.data.get("path", ".")
            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check: ensure path is within workspace
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Path does not exist: {path}")
                return

            if not full_path.is_dir():
                await self._send_error(websocket, message.request_id, f"Path is not a directory: {path}")
                return

            items = []
            for item in full_path.iterdir():
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item.relative_to(workspace_root)),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": stat.st_mtime,
                })

            # Sort: directories first, then files
            items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_LIST_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "items": items,
                    "parent": str(Path(path).parent) if path != "." else None
                }
            ))
        except Exception as e:
            logger.error(f"Failed to list directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list directory: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceListRequest) -> None:
        """Return directory listing."""
        try:
            path = validated.path
            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check: ensure path is within workspace
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Path does not exist: {path}")
                return

            if not full_path.is_dir():
                await self._send_error(websocket, message.request_id, f"Path is not a directory: {path}")
                return

            items = []
            for item in full_path.iterdir():
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item.relative_to(workspace_root)),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": stat.st_mtime,
                })

            # Sort: directories first, then files
            items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_LIST_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "items": items,
                    "parent": str(Path(path).parent) if path != "." else None
                }
            ))
        except Exception as e:
            logger.error(f"Failed to list directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to list directory: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceReadHandler(MessageHandler):
    """Handle read file requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return file content."""
        try:
            path = message.data.get("path")
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"File does not exist: {path}")
                return

            if not full_path.is_file():
                await self._send_error(websocket, message.request_id, f"Path is not a file: {path}")
                return

            file_size = full_path.stat().st_size
            MAX_READ_SIZE = 32 * 1024 * 1024
            if file_size > MAX_READ_SIZE:
                await self._send_error(websocket, message.request_id, f"File too large to preview ({file_size} bytes, max {MAX_READ_SIZE} bytes). Please download to view.")
                return

            # Read file content
            try:
                content = full_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Binary file
                content = full_path.read_bytes().hex()
                encoding = "hex"
            else:
                encoding = "utf-8"

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_READ_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "name": full_path.name,
                    "content": content,
                    "encoding": encoding,
                    "size": file_size
                }
            ))
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read file: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceReadRequest) -> None:
        """Return file content."""
        try:
            path = validated.path
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"File does not exist: {path}")
                return

            if not full_path.is_file():
                await self._send_error(websocket, message.request_id, f"Path is not a file: {path}")
                return

            file_size = full_path.stat().st_size
            MAX_READ_SIZE = 32 * 1024 * 1024
            if file_size > MAX_READ_SIZE:
                await self._send_error(websocket, message.request_id, f"File too large to preview ({file_size} bytes, max {MAX_READ_SIZE} bytes). Please download to view.")
                return

            # Read file content
            try:
                content = full_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Binary file
                content = full_path.read_bytes().hex()
                encoding = "hex"
            else:
                encoding = "utf-8"

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_READ_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "name": full_path.name,
                    "content": content,
                    "encoding": encoding,
                    "size": file_size
                }
            ))
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to read file: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceWriteHandler(MessageHandler):
    """Handle write file requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Write content to file."""
        try:
            path = message.data.get("path")
            content = message.data.get("content", "")
            encoding = message.data.get("encoding", "utf-8")

            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            if encoding == "hex":
                full_path.write_bytes(bytes.fromhex(content))
            else:
                full_path.write_text(content, encoding='utf-8')

            # Auto-update knowledge base index when markdown files in knowledge dir are written
            if path.startswith("knowledge/") and path.endswith(".md"):
                from backend.services.knowledge_engine import KnowledgeGraphEngine
                engine = KnowledgeGraphEngine(workspace_root)
                engine.update_note(path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_WRITE_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True,
                    "size": full_path.stat().st_size
                }
            ))
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to write file: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceWriteRequest) -> None:
        """Write content to file."""
        try:
            path = validated.path
            content = validated.content
            encoding = "utf-8"

            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            if encoding == "hex":
                full_path.write_bytes(bytes.fromhex(content))
            else:
                full_path.write_text(content, encoding='utf-8')

            # Auto-update knowledge base index when markdown files in knowledge dir are written
            if path.startswith("knowledge/") and path.endswith(".md"):
                from backend.services.knowledge_engine import KnowledgeGraphEngine
                engine = KnowledgeGraphEngine(workspace_root)
                engine.update_note(path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_WRITE_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True,
                    "size": full_path.stat().st_size
                }
            ))
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to write file: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceDeleteHandler(MessageHandler):
    """Handle delete file or directory requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Delete file or directory."""
        try:
            path = message.data.get("path")
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            recursive = message.data.get("recursive", False)
            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Path does not exist: {path}")
                return

            # Delete
            if full_path.is_dir():
                if recursive:
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    try:
                        full_path.rmdir()
                    except OSError:
                        await self._send_error(websocket, message.request_id, "Directory not empty, use recursive=true")
                        return
            else:
                full_path.unlink()

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_DELETE_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to delete: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceDeleteRequest) -> None:
        """Delete file or directory."""
        try:
            path = validated.path
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            recursive = False
            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_path.exists():
                await self._send_error(websocket, message.request_id, f"Path does not exist: {path}")
                return

            # Delete
            if full_path.is_dir():
                if recursive:
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    try:
                        full_path.rmdir()
                    except OSError:
                        await self._send_error(websocket, message.request_id, "Directory not empty, use recursive=true")
                        return
            else:
                full_path.unlink()

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_DELETE_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to delete: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to delete: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceMkdirHandler(MessageHandler):
    """Handle create directory requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Create directory."""
        try:
            path = message.data.get("path")
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Create directory
            full_path.mkdir(parents=True, exist_ok=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_MKDIR_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create directory: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceMkdirRequest) -> None:
        """Create directory."""
        try:
            path = validated.path
            if not path:
                await self._send_error(websocket, message.request_id, "Path is required")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            # Create directory
            full_path.mkdir(parents=True, exist_ok=True)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_MKDIR_RESULT,
                request_id=message.request_id,
                data={
                    "path": path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create directory: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceRenameHandler(MessageHandler):
    """Handle rename file or directory requests."""

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Rename file or directory."""
        try:
            old_path = message.data.get("old_path")
            new_path = message.data.get("new_path")

            if not old_path or not new_path:
                await self._send_error(websocket, message.request_id, "Both old_path and new_path are required")
                return

            workspace_root = await self._get_workspace_root()
            full_old_path = Path(workspace_root) / old_path
            full_new_path = Path(workspace_root) / new_path

            # Security check
            try:
                full_old_path = full_old_path.resolve()
                full_new_path = full_new_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_old_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: old_path outside workspace")
                    return
                if not str(full_new_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: new_path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_old_path.exists():
                await self._send_error(websocket, message.request_id, f"Source does not exist: {old_path}")
                return

            if full_new_path.exists():
                await self._send_error(websocket, message.request_id, f"Destination already exists: {new_path}")
                return

            # Rename
            full_old_path.rename(full_new_path)

            # Auto-update knowledge base index when markdown files in knowledge/notes are renamed
            if old_path.startswith("knowledge/notes"):
                from backend.services.knowledge_engine import KnowledgeGraphEngine
                engine = KnowledgeGraphEngine(workspace_root)
                
                if old_path.endswith(".md"):
                    # Single markdown file: delete old index entry and update new one
                    engine.delete_note(old_path)
                    engine.update_note(new_path)
                elif full_new_path.is_dir():
                    # Directory was moved: clean up old index entries and update new ones
                    # First, calculate what the old paths would have been and delete them
                    # We need to reconstruct the old paths based on the new paths
                    for md_file in full_new_path.rglob("*.md"):
                        new_rel_path = str(md_file.relative_to(Path(workspace_root)))
                        # Calculate the corresponding old path
                        # new_path = old_path.replace(old_dir_name, new_dir_name)
                        # So old_path = new_path.replace(new_dir_name, old_dir_name)
                        # But we need to be careful about partial matches
                        old_rel_path = new_rel_path.replace(new_path, old_path, 1)
                        engine.delete_note(old_rel_path)
                        engine.update_note(new_rel_path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_RENAME_RESULT,
                request_id=message.request_id,
                data={
                    "old_path": old_path,
                    "new_path": new_path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to rename: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to rename: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceRenameRequest) -> None:
        """Rename file or directory."""
        try:
            old_path = validated.old_path
            new_path = validated.new_path

            if not old_path or not new_path:
                await self._send_error(websocket, message.request_id, "Both old_path and new_path are required")
                return

            workspace_root = await self._get_workspace_root()
            full_old_path = Path(workspace_root) / old_path
            full_new_path = Path(workspace_root) / new_path

            # Security check
            try:
                full_old_path = full_old_path.resolve()
                full_new_path = full_new_path.resolve()
                workspace_root = Path(workspace_root).resolve()
                if not str(full_old_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: old_path outside workspace")
                    return
                if not str(full_new_path).startswith(str(workspace_root)):
                    await self._send_error(websocket, message.request_id, "Access denied: new_path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            if not full_old_path.exists():
                await self._send_error(websocket, message.request_id, f"Source does not exist: {old_path}")
                return

            if full_new_path.exists():
                await self._send_error(websocket, message.request_id, f"Destination already exists: {new_path}")
                return

            # Rename
            full_old_path.rename(full_new_path)

            # Auto-update knowledge base index when markdown files in knowledge/notes are renamed
            if old_path.startswith("knowledge/notes"):
                from backend.services.knowledge_engine import KnowledgeGraphEngine
                engine = KnowledgeGraphEngine(workspace_root)
                
                if old_path.endswith(".md"):
                    # Single markdown file: delete old index entry and update new one
                    engine.delete_note(old_path)
                    engine.update_note(new_path)
                elif full_new_path.is_dir():
                    # Directory was moved: clean up old index entries and update new ones
                    # First, calculate what the old paths would have been and delete them
                    # We need to reconstruct the old paths based on the new paths
                    for md_file in full_new_path.rglob("*.md"):
                        new_rel_path = str(md_file.relative_to(Path(workspace_root)))
                        # Calculate the corresponding old path
                        # new_path = old_path.replace(old_dir_name, new_dir_name)
                        # So old_path = new_path.replace(new_dir_name, old_dir_name)
                        # But we need to be careful about partial matches
                        old_rel_path = new_rel_path.replace(new_path, old_path, 1)
                        engine.delete_note(old_rel_path)
                        engine.update_note(new_rel_path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_RENAME_RESULT,
                request_id=message.request_id,
                data={
                    "old_path": old_path,
                    "new_path": new_path,
                    "success": True
                }
            ))
        except Exception as e:
            logger.error(f"Failed to rename: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to rename: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))


class WorkspaceWriteChunkHandler(MessageHandler):
    """Handle chunked file upload requests."""

    def __init__(self):
        self._chunk_manager: ChunkedUploadManager | None = None

    def _get_manager(self, workspace_root: str) -> ChunkedUploadManager:
        if self._chunk_manager is None:
            self._chunk_manager = ChunkedUploadManager(Path(workspace_root))
        return self._chunk_manager

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            upload_id = message.data.get("upload_id")
            path = message.data.get("path")
            chunk_index = message.data.get("chunk_index")
            total_chunks = message.data.get("total_chunks")
            hex_content = message.data.get("content", "")
            expected_md5 = message.data.get("md5")

            if not upload_id or path is None or chunk_index is None or total_chunks is None:
                await self._send_error(websocket, message.request_id, "Missing required fields")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root_resolved = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root_resolved)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            manager = self._get_manager(workspace_root)
            data = bytes.fromhex(hex_content)
            received = manager.write_chunk(upload_id, chunk_index, total_chunks, data)

            completed = False
            if received >= total_chunks:
                completed = manager.assemble_if_complete(
                    upload_id, total_chunks, path, expected_md5
                )
                if completed and path.startswith("knowledge/") and path.endswith(".md"):
                    from backend.services.knowledge_engine import KnowledgeGraphEngine
                    engine = KnowledgeGraphEngine(workspace_root)
                    engine.update_note(path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_WRITE_CHUNK_RESULT,
                request_id=message.request_id,
                data={
                    "upload_id": upload_id,
                    "chunk_index": chunk_index,
                    "received": received,
                    "total_chunks": total_chunks,
                    "completed": completed,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to write chunk: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to write chunk: {e}")

    async def handle_validated(self, websocket: WebSocket, message: WSMessage, validated: WorkspaceWriteChunkRequest) -> None:
        try:
            upload_id = validated.upload_id
            path = validated.path
            chunk_index = validated.chunk_index
            total_chunks = validated.total_chunks
            hex_content = validated.content
            expected_md5 = None

            if not upload_id or path is None or chunk_index is None or total_chunks is None:
                await self._send_error(websocket, message.request_id, "Missing required fields")
                return

            workspace_root = await self._get_workspace_root()
            full_path = Path(workspace_root) / path

            # Security check
            try:
                full_path = full_path.resolve()
                workspace_root_resolved = Path(workspace_root).resolve()
                if not str(full_path).startswith(str(workspace_root_resolved)):
                    await self._send_error(websocket, message.request_id, "Access denied: path outside workspace")
                    return
            except Exception:
                await self._send_error(websocket, message.request_id, "Invalid path")
                return

            manager = self._get_manager(workspace_root)
            data = bytes.fromhex(hex_content)
            received = manager.write_chunk(upload_id, chunk_index, total_chunks, data)

            completed = False
            if received >= total_chunks:
                completed = manager.assemble_if_complete(
                    upload_id, total_chunks, path, expected_md5
                )
                if completed and path.startswith("knowledge/") and path.endswith(".md"):
                    from backend.services.knowledge_engine import KnowledgeGraphEngine
                    engine = KnowledgeGraphEngine(workspace_root)
                    engine.update_note(path)

            await self.send_response(websocket, WSMessage(
                type=MessageType.WORKSPACE_WRITE_CHUNK_RESULT,
                request_id=message.request_id,
                data={
                    "upload_id": upload_id,
                    "chunk_index": chunk_index,
                    "received": received,
                    "total_chunks": total_chunks,
                    "completed": completed,
                }
            ))
        except Exception as e:
            logger.error(f"Failed to write chunk: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to write chunk: {e}")

    async def _get_workspace_root(self) -> str:
        from backend.utils.helpers import get_workspace_path
        return str(get_workspace_path())

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
