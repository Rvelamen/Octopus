"""Subagent data access layer for database operations."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.data.database import Database


@dataclass
class SubagentRecord:
    """Subagent record data class."""
    id: int
    name: str
    description: str
    provider_id: int | None
    model_id: int | None
    tools: list[str]
    extensions: list[str]
    max_iterations: int
    temperature: float
    system_prompt: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class AvailableToolRecord:
    """Available tool record data class."""
    id: int
    name: str
    display_name: str
    description: str
    category: str
    enabled: bool
    sort_order: int
    created_at: datetime


@dataclass
class AvailableExtensionRecord:
    """Available extension record data class."""
    id: int
    name: str
    display_name: str
    description: str
    extension_type: str
    enabled: bool
    sort_order: int
    created_at: datetime


class SubagentRepository:
    """Repository for subagent-related database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_all_subagents(self) -> list[SubagentRecord]:
        """Get all subagents."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM subagents ORDER BY name ASC"
            ).fetchall()
            return [self._row_to_subagent(row) for row in rows]

    def get_enabled_subagents(self) -> list[SubagentRecord]:
        """Get all enabled subagents."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM subagents WHERE enabled = 1 ORDER BY name ASC"
            ).fetchall()
            return [self._row_to_subagent(row) for row in rows]

    def get_subagent_by_id(self, subagent_id: int) -> Optional[SubagentRecord]:
        """Get subagent by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM subagents WHERE id = ?",
                (subagent_id,)
            ).fetchone()
            return self._row_to_subagent(row) if row else None

    def get_subagent_by_name(self, name: str) -> Optional[SubagentRecord]:
        """Get subagent by name."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM subagents WHERE name = ?",
                (name,)
            ).fetchone()
            return self._row_to_subagent(row) if row else None

    def create_subagent(
        self,
        name: str,
        description: str,
        provider_id: int | None = None,
        model_id: int | None = None,
        tools: list[str] | None = None,
        extensions: list[str] | None = None,
        max_iterations: int = 30,
        temperature: float = 0.7,
        system_prompt: str = "",
        enabled: bool = True,
    ) -> SubagentRecord:
        """Create a new subagent."""
        tools = tools or []
        extensions = extensions or []

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO subagents
                   (name, description, provider_id, model_id, tools, extensions,
                    max_iterations, temperature, system_prompt, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (name, description, provider_id, model_id, json.dumps(tools),
                 json.dumps(extensions), max_iterations, temperature, system_prompt, enabled)
            )

            row = conn.execute(
                "SELECT * FROM subagents WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()

            logger.info(f"Created subagent: {name}")
            return self._row_to_subagent(row)

    def update_subagent(
        self,
        subagent_id: int,
        name: str | None = None,
        description: str | None = None,
        provider_id: int | None = None,
        model_id: int | None = None,
        tools: list[str] | None = None,
        extensions: list[str] | None = None,
        max_iterations: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """Update subagent."""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if provider_id is not None:
            updates.append("provider_id = ?")
            params.append(provider_id)
        if model_id is not None:
            updates.append("model_id = ?")
            params.append(model_id)
        if tools is not None:
            updates.append("tools = ?")
            params.append(json.dumps(tools))
        if extensions is not None:
            updates.append("extensions = ?")
            params.append(json.dumps(extensions))
        if max_iterations is not None:
            updates.append("max_iterations = ?")
            params.append(max_iterations)
        if temperature is not None:
            updates.append("temperature = ?")
            params.append(temperature)
        if system_prompt is not None:
            updates.append("system_prompt = ?")
            params.append(system_prompt)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)

        if not updates:
            return False

        updates.append("updated_at = datetime('now', 'localtime')")
        params.append(subagent_id)

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE subagents SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def delete_subagent(self, subagent_id: int) -> bool:
        """Delete a subagent."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM subagents WHERE id = ?",
                (subagent_id,)
            )
            if cursor.rowcount > 0:
                logger.info(f"Deleted subagent id: {subagent_id}")
                return True
            return False

    def delete_subagent_by_name(self, name: str) -> bool:
        """Delete a subagent by name."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM subagents WHERE name = ?",
                (name,)
            )
            if cursor.rowcount > 0:
                logger.info(f"Deleted subagent: {name}")
                return True
            return False

    def get_subagents_with_details(self) -> list[dict[str, Any]]:
        """Get all subagents with provider and model details for frontend display."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT 
                    s.id,
                    s.name,
                    s.description,
                    s.provider_id,
                    s.model_id,
                    s.tools,
                    s.extensions,
                    s.max_iterations,
                    s.temperature,
                    s.system_prompt,
                    s.enabled,
                    s.created_at,
                    s.updated_at,
                    p.name as provider_name,
                    p.display_name as provider_display_name,
                    m.model_id as model_name,
                    m.display_name as model_display_name
                FROM subagents s
                LEFT JOIN providers p ON s.provider_id = p.id
                LEFT JOIN models m ON s.model_id = m.id
                ORDER BY s.name ASC"""
            ).fetchall()

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "providerId": row["provider_id"],
                    "modelId": row["model_id"],
                    "providerName": row["provider_name"],
                    "providerDisplayName": row["provider_display_name"],
                    "modelName": row["model_name"],
                    "modelDisplayName": row["model_display_name"],
                    "tools": json.loads(row["tools"] or "[]"),
                    "extensions": json.loads(row["extensions"] or "[]"),
                    "maxIterations": row["max_iterations"],
                    "temperature": row["temperature"],
                    "systemPrompt": row["system_prompt"],
                    "enabled": bool(row["enabled"]),
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                }
                for row in rows
            ]

    def _row_to_subagent(self, row) -> SubagentRecord:
        """Convert database row to SubagentRecord."""
        return SubagentRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            tools=json.loads(row["tools"] or "[]"),
            extensions=json.loads(row["extensions"] or "[]"),
            max_iterations=row["max_iterations"] or 30,
            temperature=row["temperature"] or 0.7,
            system_prompt=row["system_prompt"] or "",
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class AvailableToolRepository:
    """Repository for available tools database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_all_tools(self) -> list[AvailableToolRecord]:
        """Get all available tools."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM available_tools ORDER BY sort_order ASC, name ASC"
            ).fetchall()
            return [self._row_to_tool(row) for row in rows]

    def get_enabled_tools(self) -> list[AvailableToolRecord]:
        """Get all enabled tools."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM available_tools WHERE enabled = 1 ORDER BY sort_order ASC, name ASC"
            ).fetchall()
            return [self._row_to_tool(row) for row in rows]

    def get_tools_for_selection(self) -> list[dict[str, Any]]:
        """Get tools for frontend selection."""
        tools = self.get_enabled_tools()
        return [
            {
                "name": tool.name,
                "displayName": tool.display_name,
                "description": tool.description,
                "category": tool.category,
            }
            for tool in tools
        ]

    def create_tool(
        self,
        name: str,
        display_name: str,
        description: str = "",
        category: str = "filesystem",
        enabled: bool = True,
        sort_order: int = 0,
    ) -> AvailableToolRecord:
        """Create a new available tool."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO available_tools
                   (name, display_name, description, category, enabled, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (name, display_name, description, category, enabled, sort_order)
            )

            row = conn.execute(
                "SELECT * FROM available_tools WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()

            logger.info(f"Created available tool: {name}")
            return self._row_to_tool(row)

    def _row_to_tool(self, row) -> AvailableToolRecord:
        """Convert database row to AvailableToolRecord."""
        return AvailableToolRecord(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            description=row["description"] or "",
            category=row["category"] or "filesystem",
            enabled=bool(row["enabled"]),
            sort_order=row["sort_order"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class AvailableExtensionRepository:
    """Repository for available extensions database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_all_extensions(self) -> list[AvailableExtensionRecord]:
        """Get all available extensions."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM available_extensions ORDER BY sort_order ASC, name ASC"
            ).fetchall()
            return [self._row_to_extension(row) for row in rows]

    def get_enabled_extensions(self) -> list[AvailableExtensionRecord]:
        """Get all enabled extensions."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM available_extensions WHERE enabled = 1 ORDER BY sort_order ASC, name ASC"
            ).fetchall()
            return [self._row_to_extension(row) for row in rows]

    def get_extensions_for_selection(self) -> list[dict[str, Any]]:
        """Get extensions for frontend selection."""
        extensions = self.get_enabled_extensions()
        return [
            {
                "name": ext.name,
                "displayName": ext.display_name,
                "description": ext.description,
                "extensionType": ext.extension_type,
            }
            for ext in extensions
        ]

    def create_extension(
        self,
        name: str,
        display_name: str,
        description: str = "",
        extension_type: str = "skill",
        enabled: bool = True,
        sort_order: int = 0,
    ) -> AvailableExtensionRecord:
        """Create a new available extension."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO available_extensions
                   (name, display_name, description, extension_type, enabled, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (name, display_name, description, extension_type, enabled, sort_order)
            )

            row = conn.execute(
                "SELECT * FROM available_extensions WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()

            logger.info(f"Created available extension: {name}")
            return self._row_to_extension(row)

    def _row_to_extension(self, row) -> AvailableExtensionRecord:
        """Convert database row to AvailableExtensionRecord."""
        return AvailableExtensionRecord(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            description=row["description"] or "",
            extension_type=row["extension_type"] or "skill",
            enabled=bool(row["enabled"]),
            sort_order=row["sort_order"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
