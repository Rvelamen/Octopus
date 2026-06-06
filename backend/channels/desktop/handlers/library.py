"""Library (Zotero-style) handlers for Desktop channel."""

import asyncio
from pathlib import Path

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.services.library_engine import LibraryEngine
from backend.utils.helpers import get_workspace_path


class LibraryHandler(MessageHandler):
    """Handle all library-related WebSocket messages."""

    def __init__(self, bus):
        super().__init__(bus)
        workspace_root = str(get_workspace_path())
        self.engine = LibraryEngine(workspace_root)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        handler_map = {
            MessageType.LIBRARY_LIST: self._handle_list,
            MessageType.LIBRARY_GET: self._handle_get,
            MessageType.LIBRARY_CREATE: self._handle_create,
            MessageType.LIBRARY_UPDATE_META: self._handle_update_meta,
            MessageType.LIBRARY_DELETE: self._handle_delete,
            MessageType.LIBRARY_SEARCH: self._handle_search,
            MessageType.LIBRARY_ADD_ATTACHMENT: self._handle_add_attachment,
            MessageType.LIBRARY_ANNOTATIONS_LOAD: self._handle_annotations_load,
            MessageType.LIBRARY_ANNOTATIONS_SAVE: self._handle_annotations_save,
            MessageType.LIBRARY_LINK_NOTE: self._handle_link_note,
            MessageType.LIBRARY_COLLECTION_LIST: self._handle_collection_list,
            MessageType.LIBRARY_COLLECTION_CREATE: self._handle_collection_create,
            MessageType.LIBRARY_COLLECTION_UPDATE: self._handle_collection_update,
            MessageType.LIBRARY_COLLECTION_DELETE: self._handle_collection_delete,
            MessageType.LIBRARY_COLLECTION_MOVE: self._handle_collection_move,
            MessageType.LIBRARY_COLLECTION_ADD_ITEM: self._handle_collection_add_item,
            MessageType.LIBRARY_COLLECTION_REMOVE_ITEM: self._handle_collection_remove_item,
            MessageType.LIBRARY_IMPORT_DOI: self._handle_import_doi,
            MessageType.LIBRARY_IMPORT_ARXIV: self._handle_import_arxiv,
            MessageType.LIBRARY_SEARCH_CHUNKS: self._handle_search_chunks,
            MessageType.LIBRARY_AI_EXTRACT_META: self._handle_ai_extract_meta,
            MessageType.LIBRARY_GRAPH: self._handle_graph,
        }

        handler = handler_map.get(message.type)
        if handler:
            try:
                await handler(websocket, message)
            except Exception as e:
                logger.error(f"Library handler error: {e}")
                await self._send_error(websocket, message.request_id, str(e))
        else:
            await self._send_error(
                websocket, message.request_id, f"Unknown library message type: {message.type}"
            )

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await self.send_response(
            websocket,
            WSMessage(type=MessageType.ERROR, request_id=request_id, data={"error": error}),
        )

    async def _send_success(
        self, websocket: WebSocket, message: WSMessage, result_type: MessageType, data: dict
    ) -> None:
        await self.send_response(
            websocket, WSMessage(type=result_type, request_id=message.request_id, data=data)
        )

    # ------------------------------------------------------------------
    # Item handlers
    # ------------------------------------------------------------------

    async def _handle_list(self, websocket: WebSocket, message: WSMessage) -> None:
        collection_id = message.data.get("collection_id")
        query = message.data.get("query")
        limit = message.data.get("limit", 50)
        offset = message.data.get("offset", 0)
        items, total = self.engine.list_items(
            collection_id=collection_id,
            query=query,
            limit=limit,
            offset=offset,
        )
        await self._send_success(
            websocket,
            message,
            MessageType.LIBRARY_LIST_RESULT,
            {
                "items": items,
                "pagination": {"total": total, "limit": limit, "offset": offset},
            },
        )

    async def _handle_get(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        if not item_id:
            await self._send_error(websocket, message.request_id, "item_id is required")
            return
        item = self.engine.get_item(item_id)
        await self._send_success(websocket, message, MessageType.LIBRARY_GET_RESULT, {"item": item})

    async def _handle_create(self, websocket: WebSocket, message: WSMessage) -> None:
        temp_pdf_path = message.data.get("temp_pdf_path")
        metadata = message.data.get("metadata", {})
        collection_ids = message.data.get("collection_ids")

        if not temp_pdf_path:
            await self._send_error(websocket, message.request_id, "temp_pdf_path is required")
            return

        workspace = Path(self.engine.workspace_root)
        pdf_path = workspace / temp_pdf_path
        if not pdf_path.exists():
            await self._send_error(websocket, message.request_id, f"PDF not found: {temp_pdf_path}")
            return

        # Security check
        if not str(pdf_path.resolve()).startswith(str(workspace.resolve())):
            await self._send_error(
                websocket, message.request_id, "Access denied: path outside workspace"
            )
            return

        try:
            item = self.engine.create_item(
                pdf_path=pdf_path,
                metadata=metadata,
                collection_ids=collection_ids,
            )
        except Exception as e:
            logger.error(f"Failed to create library item: {e}")
            await self._send_error(websocket, message.request_id, f"Failed to create item: {e}")
            return

        # Process PDF in background: copy, hash, extract title, chunks
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self.engine._process_pdf_background, item["id"], pdf_path)

        await self._send_success(
            websocket, message, MessageType.LIBRARY_CREATE_RESULT, {"item": item}
        )

    async def _handle_update_meta(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        metadata = message.data.get("metadata", {})
        if not item_id:
            await self._send_error(websocket, message.request_id, "item_id is required")
            return
        item = self.engine.update_metadata(item_id, metadata)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_UPDATE_META_RESULT, {"item": item}
        )

    async def _handle_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        item_ids = message.data.get("item_ids")
        item_id = message.data.get("item_id")

        if item_ids and isinstance(item_ids, list):
            result = self.engine.delete_items(item_ids)
            await self._send_success(
                websocket, message, MessageType.LIBRARY_DELETE_RESULT, {"success": True, **result}
            )
        elif item_id:
            self.engine.delete_item(item_id)
            await self._send_success(
                websocket, message, MessageType.LIBRARY_DELETE_RESULT, {"success": True}
            )
        else:
            await self._send_error(websocket, message.request_id, "item_id or item_ids is required")

    async def _handle_search(self, websocket: WebSocket, message: WSMessage) -> None:
        query = message.data.get("query", "")
        collection_id = message.data.get("collection_id")
        limit = message.data.get("limit", 20)
        items, total = self.engine.list_items(query=query, collection_id=collection_id, limit=limit)
        await self._send_success(
            websocket,
            message,
            MessageType.LIBRARY_SEARCH_RESULT,
            {
                "items": items,
                "query": query,
                "pagination": {"total": total, "limit": limit, "offset": 0},
            },
        )

    async def _handle_add_attachment(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        temp_path = message.data.get("temp_path")
        message.data.get("filename")
        file_type = message.data.get("file_type", "supplementary")

        if not item_id or not temp_path:
            await self._send_error(
                websocket, message.request_id, "item_id and temp_path are required"
            )
            return

        workspace = Path(self.engine.workspace_root)
        file_path = workspace / temp_path
        if not file_path.exists():
            await self._send_error(websocket, message.request_id, f"File not found: {temp_path}")
            return

        result = self.engine.add_attachment(item_id, file_path, file_type)
        # Clean up temp file after successful attachment
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
        await self._send_success(
            websocket, message, MessageType.LIBRARY_ADD_ATTACHMENT_RESULT, {"attachment": result}
        )

    async def _handle_annotations_load(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        if not item_id:
            await self._send_error(websocket, message.request_id, "item_id is required")
            return
        try:
            annotations = self.engine.load_annotations(item_id)
            await self._send_success(
                websocket,
                message,
                MessageType.LIBRARY_ANNOTATIONS_LOAD_RESULT,
                {
                    "item_id": item_id,
                    "annotations": annotations,
                },
            )
        except Exception as e:
            logger.error(f"Failed to load annotations: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to load annotations: {e}"
            )

    async def _handle_annotations_save(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        annotations = message.data.get("annotations", [])
        if not item_id:
            await self._send_error(websocket, message.request_id, "item_id is required")
            return
        try:
            result = self.engine.save_annotations(item_id, annotations)
            await self._send_success(
                websocket,
                message,
                MessageType.LIBRARY_ANNOTATIONS_SAVE_RESULT,
                {
                    "item_id": item_id,
                    "saved": result["saved"],
                },
            )
        except Exception as e:
            logger.error(f"Failed to save annotations: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to save annotations: {e}"
            )

    async def _handle_link_note(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        note_path = message.data.get("note_path")
        relation = message.data.get("relation", "manual")
        if not item_id or not note_path:
            await self._send_error(
                websocket, message.request_id, "item_id and note_path are required"
            )
            return
        result = self.engine.link_note(item_id, note_path, relation)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_LINK_NOTE_RESULT, {"link": result}
        )

    # ------------------------------------------------------------------
    # Collection handlers
    # ------------------------------------------------------------------

    async def _handle_collection_list(self, websocket: WebSocket, message: WSMessage) -> None:
        flat = message.data.get("flat", False)
        collections = self.engine.list_collections(flat=flat)
        await self._send_success(
            websocket,
            message,
            MessageType.LIBRARY_COLLECTION_LIST_RESULT,
            {
                "collections": collections,
            },
        )

    async def _handle_collection_create(self, websocket: WebSocket, message: WSMessage) -> None:
        name = message.data.get("name")
        parent_id = message.data.get("parent_id")
        color = message.data.get("color")
        if not name:
            await self._send_error(websocket, message.request_id, "name is required")
            return
        result = self.engine.create_collection(name, parent_id, color)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_COLLECTION_CREATE_RESULT, {"collection": result}
        )

    async def _handle_collection_update(self, websocket: WebSocket, message: WSMessage) -> None:
        collection_id = message.data.get("id")
        name = message.data.get("name")
        color = message.data.get("color")
        if not collection_id:
            await self._send_error(websocket, message.request_id, "id is required")
            return
        result = self.engine.update_collection(collection_id, name, color)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_COLLECTION_UPDATE_RESULT, {"collection": result}
        )

    async def _handle_collection_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        collection_id = message.data.get("id")
        if not collection_id:
            await self._send_error(websocket, message.request_id, "id is required")
            return
        self.engine.delete_collection(collection_id)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_COLLECTION_DELETE_RESULT, {"success": True}
        )

    async def _handle_collection_move(self, websocket: WebSocket, message: WSMessage) -> None:
        collection_id = message.data.get("id")
        new_parent_id = message.data.get("new_parent_id")
        if not collection_id:
            await self._send_error(websocket, message.request_id, "id is required")
            return
        result = self.engine.move_collection(collection_id, new_parent_id)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_COLLECTION_MOVE_RESULT, {"collection": result}
        )

    async def _handle_collection_add_item(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        collection_id = message.data.get("collection_id")
        if not item_id or not collection_id:
            await self._send_error(
                websocket, message.request_id, "item_id and collection_id are required"
            )
            return
        self.engine.add_to_collection(item_id, collection_id)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_COLLECTION_ADD_ITEM_RESULT, {"success": True}
        )

    async def _handle_collection_remove_item(
        self, websocket: WebSocket, message: WSMessage
    ) -> None:
        item_id = message.data.get("item_id")
        collection_id = message.data.get("collection_id")
        if not item_id or not collection_id:
            await self._send_error(
                websocket, message.request_id, "item_id and collection_id are required"
            )
            return
        self.engine.remove_from_collection(item_id, collection_id)
        await self._send_success(
            websocket, message, MessageType.LIBRARY_COLLECTION_REMOVE_ITEM_RESULT, {"success": True}
        )

    # ------------------------------------------------------------------
    # Import handlers
    # ------------------------------------------------------------------

    async def _handle_import_doi(self, websocket: WebSocket, message: WSMessage) -> None:
        doi = message.data.get("doi")
        collection_ids = message.data.get("collection_ids")
        if not doi:
            await self._send_error(websocket, message.request_id, "doi is required")
            return

        try:
            metadata = await self.engine.fetch_metadata_by_doi(doi)
        except Exception as e:
            await self._send_error(
                websocket, message.request_id, f"Failed to fetch DOI metadata: {e}"
            )
            return

        # For DOI import without PDF, create item without PDF file
        item = self.engine.create_item(
            pdf_path=None,
            metadata=metadata,
            collection_ids=collection_ids,
        )
        await self._send_success(
            websocket, message, MessageType.LIBRARY_IMPORT_DOI_RESULT, {"item": item}
        )

    async def _handle_import_arxiv(self, websocket: WebSocket, message: WSMessage) -> None:
        arxiv_id = message.data.get("arxiv_id")
        collection_ids = message.data.get("collection_ids")
        if not arxiv_id:
            await self._send_error(websocket, message.request_id, "arxiv_id is required")
            return

        try:
            metadata = await asyncio.wait_for(
                self.engine.fetch_metadata_by_arxiv(arxiv_id),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            await self._send_error(
                websocket,
                message.request_id,
                "Fetching arXiv metadata timed out. Please try again.",
            )
            return
        except Exception as e:
            await self._send_error(
                websocket, message.request_id, f"Failed to fetch arXiv metadata: {e}"
            )
            return

        # Normalize arxiv_id for safe file path (metadata already parsed the clean ID)
        clean_arxiv_id = metadata.get("arxiv_id") or arxiv_id
        pdf_path = self.engine.library_dir / f"_tmp_{clean_arxiv_id}.pdf"
        try:
            await asyncio.wait_for(
                self.engine.download_arxiv_pdf(clean_arxiv_id, pdf_path),
                timeout=60.0,
            )
            item = self.engine.create_item(
                pdf_path=pdf_path,
                metadata=metadata,
                collection_ids=collection_ids,
            )

            # Process PDF in background: copy, hash, extract title, chunks
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self.engine._process_pdf_background, item["id"], pdf_path)

            await self._send_success(
                websocket, message, MessageType.LIBRARY_IMPORT_ARXIV_RESULT, {"item": item}
            )
        except asyncio.TimeoutError:
            if pdf_path.exists():
                pdf_path.unlink()
            await self._send_error(
                websocket, message.request_id, "Downloading arXiv PDF timed out. Please try again."
            )
        except Exception as e:
            if pdf_path.exists():
                pdf_path.unlink()
            await self._send_error(
                websocket, message.request_id, f"Failed to import arXiv paper: {e}"
            )

    async def _handle_search_chunks(self, websocket: WebSocket, message: WSMessage) -> None:
        query = message.data.get("query", "")
        limit = message.data.get("limit", 20)
        if not query.strip():
            await self._send_error(websocket, message.request_id, "query is required")
            return
        try:
            results = self.engine.search_chunks(query.strip(), limit)
            await self._send_success(
                websocket,
                message,
                MessageType.LIBRARY_SEARCH_CHUNKS_RESULT,
                {
                    "results": results,
                    "query": query,
                },
            )
        except Exception as e:
            await self._send_error(websocket, message.request_id, f"Failed to search chunks: {e}")

    async def _handle_graph(self, websocket: WebSocket, message: WSMessage) -> None:
        collection_id = message.data.get("collection_id")
        center_item_id = message.data.get("center_item_id")
        limit = message.data.get("limit", 300)
        try:
            graph = self.engine.get_paper_graph(
                collection_id=collection_id,
                center_item_id=center_item_id,
                limit=limit,
            )
            await self._send_success(websocket, message, MessageType.LIBRARY_GRAPH_RESULT, graph)
        except Exception as e:
            logger.error(f"Failed to get library graph: {e}")
            await self._send_error(
                websocket, message.request_id, f"Failed to get library graph: {e}"
            )

    async def _handle_ai_extract_meta(self, websocket: WebSocket, message: WSMessage) -> None:
        item_id = message.data.get("item_id")
        if not item_id:
            await self._send_error(websocket, message.request_id, "item_id is required")
            return
        try:
            metadata = await self.engine.ai_extract_metadata(item_id)
            await self._send_success(
                websocket,
                message,
                MessageType.LIBRARY_AI_EXTRACT_META_RESULT,
                {
                    "metadata": metadata,
                },
            )
        except Exception as e:
            logger.error(f"AI extract meta error: {e}")
            await self._send_error(websocket, message.request_id, f"AI extraction failed: {e}")
