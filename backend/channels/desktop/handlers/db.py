"""Handlers for user-defined database table operations."""

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.handlers.base import MessageHandler
from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.data import Database
from backend.data.db_store import DBRepository


class DBTableHandler(MessageHandler):
    """Handle db_table_* and db_record_* messages."""

    def __init__(self, bus, db: Database | None = None):
        super().__init__(bus)
        self.db = db or Database()
        self.repo = DBRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        handler_map = {
            MessageType.DB_TABLE_LIST: self._handle_table_list,
            MessageType.DB_TABLE_CREATE: self._handle_table_create,
            MessageType.DB_TABLE_GET: self._handle_table_get,
            MessageType.DB_TABLE_UPDATE: self._handle_table_update,
            MessageType.DB_TABLE_DELETE: self._handle_table_delete,
            MessageType.DB_RECORD_LIST: self._handle_record_list,
            MessageType.DB_RECORD_CREATE: self._handle_record_create,
            MessageType.DB_RECORD_UPDATE: self._handle_record_update,
            MessageType.DB_RECORD_DELETE: self._handle_record_delete,
            MessageType.DB_RECORD_SEARCH: self._handle_record_search,
        }

        handler = handler_map.get(message.type)
        if handler:
            await handler(websocket, message)
        else:
            await websocket.send_json(
                WSMessage(
                    type=MessageType.ERROR,
                    request_id=message.request_id,
                    data={"error": f"Unsupported DB operation: {message.type.value}"},
                ).to_dict()
            )

    # ── Table Operations ──

    async def _handle_table_list(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            tables = self.repo.list_tables()
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_TABLE_LIST,
                    request_id=message.request_id,
                    data={
                        "tables": [
                            {
                                "id": t.id,
                                "name": t.name,
                                "description": t.description,
                                "fields": self.repo._safe_json_load(t.fields_json),
                                "created_at": t.created_at,
                                "updated_at": t.updated_at,
                            }
                            for t in tables
                        ]
                    },
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] list_tables error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_table_create(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            name = data.get("name", "").strip()
            description = data.get("description", "").strip()
            fields = data.get("fields", [])

            if not name:
                raise ValueError("Table name is required")
            if not fields:
                raise ValueError("At least one field is required")

            table = self.repo.create_table(name, description, fields)
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_TABLE_CREATE,
                    request_id=message.request_id,
                    data={
                        "id": table.id,
                        "name": table.name,
                        "description": table.description,
                        "fields": self.repo._safe_json_load(table.fields_json),
                        "created_at": table.created_at,
                        "updated_at": table.updated_at,
                    },
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] create_table error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_table_get(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            name = data.get("name", "").strip()
            table = self.repo.get_table(name)
            if not table:
                raise ValueError(f"Table '{name}' not found")
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_TABLE_GET,
                    request_id=message.request_id,
                    data={
                        "id": table.id,
                        "name": table.name,
                        "description": table.description,
                        "fields": self.repo._safe_json_load(table.fields_json),
                        "created_at": table.created_at,
                        "updated_at": table.updated_at,
                    },
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] get_table error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_table_update(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            table_id = data.get("id")
            name = data.get("name")
            description = data.get("description")
            fields = data.get("fields")

            if not table_id:
                raise ValueError("Table id is required")

            table = self.repo.update_table(
                table_id,
                name=name.strip() if name else None,
                description=description.strip() if description else None,
                fields=fields if fields else None,
            )
            if not table:
                raise ValueError(f"Table id={table_id} not found")

            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_TABLE_UPDATE,
                    request_id=message.request_id,
                    data={
                        "id": table.id,
                        "name": table.name,
                        "description": table.description,
                        "fields": self.repo._safe_json_load(table.fields_json),
                        "created_at": table.created_at,
                        "updated_at": table.updated_at,
                    },
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] update_table error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_table_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            name = data.get("name", "").strip()
            if not name:
                raise ValueError("Table name is required")
            self.repo.delete_table(name)
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_TABLE_DELETE,
                    request_id=message.request_id,
                    data={"success": True},
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] delete_table error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    # ── Record Operations ──

    async def _handle_record_list(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            table_name = data.get("table_name", "").strip()
            page = data.get("page", 1)
            page_size = data.get("page_size", 20)
            sort_field = data.get("sort_field", "created_at")
            sort_order = data.get("sort_order", "desc")

            if not table_name:
                raise ValueError("table_name is required")

            result = self.repo.list_records(table_name, page, page_size, sort_field, sort_order)
            result["records"] = [
                {
                    "id": r.id,
                    "table_name": r.table_name,
                    "record_data": r.record_data,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in result["records"]
            ]
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_RECORD_LIST, request_id=message.request_id, data=result
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] record_list error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_record_create(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            table_name = data.get("table_name", "").strip()
            record_data = data.get("record_data", {})

            if not table_name:
                raise ValueError("table_name is required")

            # Get table fields to handle auto-increment
            table = self.repo.get_table(table_name)
            fields = self.repo._safe_json_load(table.fields_json) if table else []

            record = self.repo.create_record(table_name, record_data, fields)
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_RECORD_CREATE,
                    request_id=message.request_id,
                    data={
                        "id": record.id,
                        "table_name": record.table_name,
                        "record_data": record.record_data,
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                    },
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] record_create error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_record_update(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            record_id = data.get("id")
            record_data = data.get("record_data", {})

            if not record_id:
                raise ValueError("Record id is required")

            record = self.repo.update_record(record_id, record_data)
            if not record:
                raise ValueError(f"Record id={record_id} not found")

            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_RECORD_UPDATE,
                    request_id=message.request_id,
                    data={
                        "id": record.id,
                        "table_name": record.table_name,
                        "record_data": record.record_data,
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                    },
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] record_update error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_record_delete(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            record_id = data.get("id")
            if not record_id:
                raise ValueError("Record id is required")
            self.repo.delete_record(record_id)
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_RECORD_DELETE,
                    request_id=message.request_id,
                    data={"success": True},
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] record_delete error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    async def _handle_record_search(self, websocket: WebSocket, message: WSMessage) -> None:
        try:
            data = message.data or {}
            table_name = data.get("table_name", "").strip()
            keyword = data.get("keyword", "").strip()
            page = data.get("page", 1)
            page_size = data.get("page_size", 20)

            if not table_name:
                raise ValueError("table_name is required")

            result = self.repo.search_records(table_name, keyword, page, page_size)
            result["records"] = [
                {
                    "id": r.id,
                    "table_name": r.table_name,
                    "record_data": r.record_data,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in result["records"]
            ]
            await websocket.send_json(
                WSMessage(
                    type=MessageType.DB_RECORD_SEARCH, request_id=message.request_id, data=result
                ).to_dict()
            )
        except Exception as e:
            logger.error(f"[DBTableHandler] record_search error: {e}")
            await self._send_error(websocket, message.request_id, str(e))

    # ── Helpers ──

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        await websocket.send_json(
            WSMessage(
                type=MessageType.ERROR, request_id=request_id, data={"error": error}
            ).to_dict()
        )
