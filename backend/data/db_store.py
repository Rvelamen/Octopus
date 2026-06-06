"""Repository for user-defined database tables and records."""

import json
from dataclasses import dataclass
from typing import Any

from backend.data.database import Database


@dataclass
class UserTableRecord:
    id: int
    name: str
    description: str
    fields_json: str
    created_at: str
    updated_at: str


@dataclass
class UserDataRecord:
    id: int
    table_name: str
    record_data: dict
    created_at: str
    updated_at: str


class DBRepository:
    """Repository for user-defined tables and their data.

    All user tables share a single physical table (user_data_records)
    with JSON storage. table_name is used as the logical separator.
    """

    def __init__(self, db: Database):
        self.db = db

    # ── Table Management ──

    def list_tables(self) -> list[UserTableRecord]:
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, description, fields_json, created_at, updated_at "
                "FROM user_tables ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_table(row) for row in rows]

    def get_table(self, name: str) -> UserTableRecord | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, description, fields_json, created_at, updated_at "
                "FROM user_tables WHERE name = ?",
                (name,),
            ).fetchone()
            return self._row_to_table(row) if row else None

    def get_table_by_id(self, table_id: int) -> UserTableRecord | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, description, fields_json, created_at, updated_at "
                "FROM user_tables WHERE id = ?",
                (table_id,),
            ).fetchone()
            return self._row_to_table(row) if row else None

    def create_table(self, name: str, description: str, fields: list[dict]) -> UserTableRecord:
        fields_json = json.dumps(fields, ensure_ascii=False)
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO user_tables (name, description, fields_json) VALUES (?, ?, ?)",
                (name, description, fields_json),
            )
            table_id = cursor.lastrowid
            row = conn.execute(
                "SELECT id, name, description, fields_json, created_at, updated_at "
                "FROM user_tables WHERE id = ?",
                (table_id,),
            ).fetchone()
            return self._row_to_table(row)

    def update_table(
        self,
        table_id: int,
        name: str | None = None,
        description: str | None = None,
        fields: list[dict] | None = None,
    ) -> UserTableRecord | None:
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if fields is not None:
            updates.append("fields_json = ?")
            params.append(json.dumps(fields, ensure_ascii=False))
        if not updates:
            return self.get_table_by_id(table_id)

        params.append(table_id)
        with self.db._get_connection() as conn:
            conn.execute(
                f"UPDATE user_tables SET {', '.join(updates)}, updated_at = (datetime('now', 'localtime')) WHERE id = ?",
                params,
            )
            return self.get_table_by_id(table_id)

    def delete_table(self, name: str) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM user_data_records WHERE table_name = ?", (name,))
            conn.execute("DELETE FROM user_tables WHERE name = ?", (name,))

    # ── Record CRUD ──

    def list_records(
        self,
        table_name: str,
        page: int = 1,
        page_size: int = 20,
        sort_field: str = "created_at",
        sort_order: str = "desc",
    ) -> dict:
        offset = (page - 1) * page_size
        order_clause = f"ORDER BY {self._safe_identifier(sort_field)} {sort_order.upper()}"

        with self.db._get_connection() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) as total FROM user_data_records WHERE table_name = ?",
                (table_name,),
            ).fetchone()
            total = total_row["total"] if total_row else 0

            rows = conn.execute(
                f"SELECT id, table_name, record_data, created_at, updated_at "
                f"FROM user_data_records WHERE table_name = ? {order_clause} LIMIT ? OFFSET ?",
                (table_name, page_size, offset),
            ).fetchall()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "records": [self._row_to_data(row) for row in rows],
            }

    def create_record(
        self, table_name: str, data: dict, fields: list[dict] | None = None
    ) -> UserDataRecord:
        # Handle auto-increment fields
        if fields:
            auto_inc_fields = [f for f in fields if f.get("autoIncrement")]
            if auto_inc_fields:
                with self.db._get_connection() as conn:
                    for field in auto_inc_fields:
                        field_name = field["name"]
                        # Find max value for this field in the table
                        rows = conn.execute(
                            "SELECT record_data FROM user_data_records WHERE table_name = ?",
                            (table_name,),
                        ).fetchall()
                        max_val = 0
                        for row in rows:
                            try:
                                record = json.loads(row["record_data"] or "{}")
                                val = record.get(field_name)
                                if isinstance(val, (int, float)) and val > max_val:
                                    max_val = int(val)
                            except (json.JSONDecodeError, ValueError):
                                continue
                        data[field_name] = max_val + 1

        record_data = json.dumps(data, ensure_ascii=False)
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO user_data_records (table_name, record_data) VALUES (?, ?)",
                (table_name, record_data),
            )
            record_id = cursor.lastrowid
            row = conn.execute(
                "SELECT id, table_name, record_data, created_at, updated_at "
                "FROM user_data_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            return self._row_to_data(row)

    def get_record(self, record_id: int) -> UserDataRecord | None:
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT id, table_name, record_data, created_at, updated_at "
                "FROM user_data_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            return self._row_to_data(row) if row else None

    def update_record(self, record_id: int, data: dict) -> UserDataRecord | None:
        record_data = json.dumps(data, ensure_ascii=False)
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE user_data_records SET record_data = ?, updated_at = (datetime('now', 'localtime')) WHERE id = ?",
                (record_data, record_id),
            )
            return self.get_record(record_id)

    def delete_record(self, record_id: int) -> None:
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM user_data_records WHERE id = ?", (record_id,))

    def search_records(
        self, table_name: str, keyword: str, page: int = 1, page_size: int = 20
    ) -> dict:
        """Full-text search across record_data JSON."""
        offset = (page - 1) * page_size
        pattern = f"%{keyword}%"

        with self.db._get_connection() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) as total FROM user_data_records WHERE table_name = ? AND record_data LIKE ?",
                (table_name, pattern),
            ).fetchone()
            total = total_row["total"] if total_row else 0

            rows = conn.execute(
                "SELECT id, table_name, record_data, created_at, updated_at "
                "FROM user_data_records WHERE table_name = ? AND record_data LIKE ? "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (table_name, pattern, page_size, offset),
            ).fetchall()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "records": [self._row_to_data(row) for row in rows],
            }

    # ── Helpers ──

    def _row_to_table(self, row) -> UserTableRecord:
        return UserTableRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            fields_json=row["fields_json"] or "[]",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_data(self, row) -> UserDataRecord:
        raw = row["record_data"] or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        return UserDataRecord(
            id=row["id"],
            table_name=row["table_name"],
            record_data=data,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _safe_identifier(name: str) -> str:
        """Sanitize column/table name to prevent SQL injection."""
        if not name or not name.replace("_", "").isalnum():
            return "created_at"
        return name

    @staticmethod
    def _safe_json_load(raw: str) -> Any:
        """Safely load JSON string, return empty list on error."""
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
