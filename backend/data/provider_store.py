"""Provider and Model data access layer."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from backend.data.database import Database


@dataclass
class ProviderRecord:
    """Provider record data class."""
    id: int
    name: str
    display_name: str
    provider_type: str
    api_key: str
    api_host: str
    api_version: str
    enabled: bool
    is_system: bool
    sort_order: int
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class ModelRecord:
    """Model record data class."""
    id: int
    provider_id: int
    model_id: str
    display_name: str
    model_types: list[str]
    group_name: str
    max_tokens: int
    context_window: int
    supports_vision: bool
    supports_function_calling: bool
    supports_streaming: bool
    enabled: bool
    is_default: bool
    description: str | None
    pricing_json: dict[str, Any] | None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProviderRepository:
    """Repository for provider-related database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_all_providers(self) -> list[ProviderRecord]:
        """Get all providers."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM providers ORDER BY sort_order ASC, display_name ASC"
            ).fetchall()
            return [self._row_to_provider(row) for row in rows]

    def get_enabled_providers(self) -> list[ProviderRecord]:
        """Get all enabled providers."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM providers WHERE enabled = 1 ORDER BY sort_order ASC, display_name ASC"
            ).fetchall()
            return [self._row_to_provider(row) for row in rows]

    def get_provider_by_id(self, provider_id: int) -> Optional[ProviderRecord]:
        """Get provider by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM providers WHERE id = ?",
                (provider_id,)
            ).fetchone()
            return self._row_to_provider(row) if row else None

    def get_provider_by_name(self, name: str) -> Optional[ProviderRecord]:
        """Get provider by name."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM providers WHERE name = ?",
                (name,)
            ).fetchone()
            return self._row_to_provider(row) if row else None

    def add_provider(
        self,
        name: str,
        display_name: str,
        provider_type: str,
        api_key: str = "",
        api_host: str = "",
        api_version: str = "",
        enabled: bool = False,
        is_system: bool = False,
        sort_order: int | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> ProviderRecord:
        """Add a new provider.

        If sort_order is not provided, the new provider will be placed at the top
        by using a sort_order smaller than all existing providers.
        """
        config_json = config_json or {}

        with self.db._get_connection() as conn:
            # If sort_order not provided, place new provider at the top
            if sort_order is None:
                row = conn.execute(
                    "SELECT MIN(sort_order) as min_order FROM providers"
                ).fetchone()
                min_order = row["min_order"] if row and row["min_order"] is not None else 0
                sort_order = min_order - 1

            cursor = conn.execute(
                """INSERT INTO providers
                   (name, display_name, provider_type, api_key, api_host, api_version,
                    enabled, is_system, sort_order, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (name, display_name, provider_type, api_key, api_host, api_version,
                 enabled, is_system, sort_order, json.dumps(config_json))
            )

            row = conn.execute(
                "SELECT * FROM providers WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()

            logger.info(f"Added provider: {name}")
            return self._row_to_provider(row)

    def update_provider(
        self,
        provider_id: int,
        api_key: str | None = None,
        api_host: str | None = None,
        api_version: str | None = None,
        enabled: bool | None = None,
        sort_order: int | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Update provider."""
        updates = []
        params = []

        if api_key is not None:
            updates.append("api_key = ?")
            params.append(api_key)
        if api_host is not None:
            updates.append("api_host = ?")
            params.append(api_host)
        if api_version is not None:
            updates.append("api_version = ?")
            params.append(api_version)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)
        if config_json is not None:
            updates.append("config_json = ?")
            params.append(json.dumps(config_json))

        if not updates:
            return False

        updates.append("updated_at = datetime('now', 'localtime')")
        params.append(provider_id)

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE providers SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def delete_provider(self, provider_id: int) -> bool:
        """Delete a provider and all its models (cascade)."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM providers WHERE id = ?",
                (provider_id,)
            )
            if cursor.rowcount > 0:
                logger.info(f"Deleted provider id: {provider_id}")
                return True
            return False

    def delete_provider_by_name(self, name: str) -> bool:
        """Delete a provider by name."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM providers WHERE name = ?",
                (name,)
            )
            if cursor.rowcount > 0:
                logger.info(f"Deleted provider: {name}")
                return True
            return False

    def _row_to_provider(self, row) -> ProviderRecord:
        """Convert database row to ProviderRecord."""
        return ProviderRecord(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            provider_type=row["provider_type"],
            api_key=row["api_key"] or "",
            api_host=row["api_host"] or "",
            api_version=row["api_version"] or "",
            enabled=bool(row["enabled"]),
            is_system=bool(row["is_system"]),
            sort_order=row["sort_order"] or 0,
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class ModelRepository:
    """Repository for model-related database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_models_by_provider(self, provider_id: int) -> list[ModelRecord]:
        """Get all models for a provider."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM models
                   WHERE provider_id = ?
                   ORDER BY group_name ASC, display_name ASC""",
                (provider_id,)
            ).fetchall()
            return [self._row_to_model(row) for row in rows]

    def get_enabled_models_by_provider(self, provider_id: int) -> list[ModelRecord]:
        """Get all enabled models for a provider."""
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM models
                   WHERE provider_id = ? AND enabled = 1
                   ORDER BY group_name ASC, display_name ASC""",
                (provider_id,)
            ).fetchall()
            return [self._row_to_model(row) for row in rows]

    def get_model_by_id(self, model_id: int) -> Optional[ModelRecord]:
        """Get model by ID."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE id = ?",
                (model_id,)
            ).fetchone()
            return self._row_to_model(row) if row else None

    def get_model_by_provider_and_model_id(
        self, provider_id: int, model_id: str
    ) -> Optional[ModelRecord]:
        """Get model by provider_id and model_id."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE provider_id = ? AND model_id = ?",
                (provider_id, model_id)
            ).fetchone()
            return self._row_to_model(row) if row else None

    def get_default_model(self, provider_id: int) -> Optional[ModelRecord]:
        """Get default model for a provider."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE provider_id = ? AND is_default = 1 LIMIT 1",
                (provider_id,)
            ).fetchone()
            return self._row_to_model(row) if row else None

    def add_model(
        self,
        provider_id: int,
        model_id: str,
        display_name: str,
        model_types: list[str] | None = None,
        group_name: str = "Chat Models",
        max_tokens: int = 4096,
        context_window: int = 128000,
        supports_vision: bool = False,
        supports_function_calling: bool = True,
        supports_streaming: bool = True,
        enabled: bool = True,
        is_default: bool = False,
        config_json: dict[str, Any] | None = None,
    ) -> ModelRecord:
        """Add a new model."""
        config_json = config_json or {}
        model_types = model_types or ["chat"]

        if is_default:
            self._clear_default_models(provider_id)

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO models
                   (provider_id, model_id, display_name, model_types, group_name,
                    max_tokens, context_window, supports_vision, supports_function_calling,
                    supports_streaming, enabled, is_default, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                (provider_id, model_id, display_name, json.dumps(model_types), group_name,
                 max_tokens, context_window, supports_vision, supports_function_calling,
                 supports_streaming, enabled, is_default, json.dumps(config_json))
            )

            row = conn.execute(
                "SELECT * FROM models WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()

            logger.info(f"Added model: {model_id} for provider {provider_id}")
            return self._row_to_model(row)

    def update_model(
        self,
        model_id: int,
        display_name: str | None = None,
        model_types: list[str] | None = None,
        group_name: str | None = None,
        max_tokens: int | None = None,
        context_window: int | None = None,
        supports_vision: bool | None = None,
        supports_function_calling: bool | None = None,
        supports_streaming: bool | None = None,
        enabled: bool | None = None,
        is_default: bool | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Update model."""
        if is_default:
            model = self.get_model_by_id(model_id)
            if model:
                self._clear_default_models(model.provider_id)

        updates = []
        params = []

        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if model_types is not None:
            updates.append("model_types = ?")
            params.append(json.dumps(model_types))
        if group_name is not None:
            updates.append("group_name = ?")
            params.append(group_name)
        if max_tokens is not None:
            updates.append("max_tokens = ?")
            params.append(max_tokens)
        if context_window is not None:
            updates.append("context_window = ?")
            params.append(context_window)
        if supports_vision is not None:
            updates.append("supports_vision = ?")
            params.append(supports_vision)
        if supports_function_calling is not None:
            updates.append("supports_function_calling = ?")
            params.append(supports_function_calling)
        if supports_streaming is not None:
            updates.append("supports_streaming = ?")
            params.append(supports_streaming)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)
        if is_default is not None:
            updates.append("is_default = ?")
            params.append(is_default)
        if config_json is not None:
            updates.append("config_json = ?")
            params.append(json.dumps(config_json))

        if not updates:
            return False

        updates.append("updated_at = datetime('now', 'localtime')")
        params.append(model_id)

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE models SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def delete_model(self, model_id: int) -> bool:
        """Delete a model."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM models WHERE id = ?",
                (model_id,)
            )
            if cursor.rowcount > 0:
                logger.info(f"Deleted model id: {model_id}")
                return True
            return False

    def _clear_default_models(self, provider_id: int) -> None:
        """Clear default flag from all models of a provider."""
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE models SET is_default = 0 WHERE provider_id = ?",
                (provider_id,)
            )

    def _row_to_model(self, row) -> ModelRecord:
        """Convert database row to ModelRecord."""
        # Parse model_types from JSON string
        # sqlite3.Row supports both dict-style access and index access
        model_types_str = row["model_types"] if "model_types" in row.keys() else None
        try:
            model_types = json.loads(model_types_str) if model_types_str else None
        except (json.JSONDecodeError, TypeError):
            model_types = None
        
        # Fallback to default if model_types is not set
        if not model_types:
            model_types = ["chat"]
        
        return ModelRecord(
            id=row["id"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            display_name=row["display_name"],
            model_types=model_types,
            group_name=row["group_name"] or "Chat Models",
            max_tokens=row["max_tokens"] or 4096,
            context_window=row["context_window"] or 128000,
            supports_vision=bool(row["supports_vision"]),
            supports_function_calling=bool(row["supports_function_calling"]),
            supports_streaming=bool(row["supports_streaming"]),
            enabled=bool(row["enabled"]),
            is_default=bool(row["is_default"]),
            description=row["description"] if "description" in row.keys() else None,
            pricing_json=json.loads(row["pricing_json"]) if "pricing_json" in row.keys() and row["pricing_json"] else None,
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class SettingsRepository:
    """Repository for user settings database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM user_settings WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else None

    def get_setting_typed(self, key: str) -> Any:
        """Get a setting value with type conversion."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT value, value_type FROM user_settings WHERE key = ?",
                (key,)
            ).fetchone()

            if not row:
                return None

            value = row["value"]
            value_type = row["value_type"] or "string"

            if value_type == "boolean":
                return value == "true" or value == "1"
            elif value_type == "number":
                try:
                    return float(value) if "." in value else int(value)
                except (ValueError, TypeError):
                    return None
            elif value_type == "json":
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return None
            return value

    def set_setting(
        self, key: str, value: Any, value_type: str = "string"
    ) -> bool:
        """Set a setting value."""
        if value_type == "string":
            str_value = str(value) if value is not None else ""
        elif value_type == "boolean":
            str_value = "true" if value else "false"
        elif value_type == "number":
            str_value = str(value)
        elif value_type == "json":
            str_value = json.dumps(value) if value is not None else ""
        else:
            str_value = str(value) if value is not None else ""

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO user_settings (key, value, value_type, updated_at)
                   VALUES (?, ?, ?, datetime('now', 'localtime'))
                   ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   value_type = excluded.value_type,
                   updated_at = excluded.updated_at""",
                (key, str_value, value_type)
            )
            return cursor.rowcount > 0

    def delete_setting(self, key: str) -> bool:
        """Delete a setting."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM user_settings WHERE key = ?",
                (key,)
            )
            return cursor.rowcount > 0

    def get_all_settings(self) -> dict[str, Any]:
        """Get all settings as a dictionary."""
        with self.db._get_connection() as conn:
            rows = conn.execute("SELECT key, value, value_type FROM user_settings").fetchall()
            result = {}
            for row in rows:
                key = row["key"]
                value = row["value"]
                value_type = row["value_type"] or "string"

                if value_type == "boolean":
                    result[key] = value == "true" or value == "1"
                elif value_type == "number":
                    try:
                        result[key] = float(value) if "." in value else int(value)
                    except (ValueError, TypeError):
                        result[key] = value
                elif value_type == "json":
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
                else:
                    result[key] = value
            return result


@dataclass
class AgentDefaultsRecord:
    """Agent defaults record data class."""
    id: int
    default_provider_id: int | None
    default_model_id: int | None
    workspace_path: str
    max_tokens: int
    temperature: float
    max_iterations: int
    context_compression_enabled: bool
    context_compression_turns: int
    context_compression_token_threshold: int
    llm_max_retries: int
    llm_retry_base_delay: float
    llm_retry_max_delay: float
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentDefaultsRepository:
    """Repository for agent defaults database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_or_create_defaults(self) -> AgentDefaultsRecord:
        """Get agent defaults, create if not exists."""
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_defaults LIMIT 1").fetchone()
            if row:
                return self._row_to_agent_defaults(row)

            # Create default record
            cursor = conn.execute(
                """INSERT INTO agent_defaults
                   (workspace_path, max_tokens, temperature, max_iterations,
                    context_compression_enabled, context_compression_turns,
                    config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""",
                ("", 8192, 0.7, 20, False, 10, "{}")
            )

            row = conn.execute(
                "SELECT * FROM agent_defaults WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            return self._row_to_agent_defaults(row)

    def get_agent_defaults(self) -> AgentDefaultsRecord | None:
        """Get agent defaults."""
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT * FROM agent_defaults LIMIT 1").fetchone()
            return self._row_to_agent_defaults(row) if row else None

    def update_agent_defaults(
        self,
        default_provider_id: int | None = None,
        default_model_id: int | None = None,
        workspace_path: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        max_iterations: int | None = None,
        context_compression_enabled: bool | None = None,
        context_compression_turns: int | None = None,
        context_compression_token_threshold: int | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Update agent defaults."""
        updates = []
        params = []

        if default_provider_id is not None:
            updates.append("default_provider_id = ?")
            params.append(default_provider_id)
        if default_model_id is not None:
            updates.append("default_model_id = ?")
            params.append(default_model_id)
        if workspace_path is not None:
            updates.append("workspace_path = ?")
            params.append(workspace_path)
        if max_tokens is not None:
            updates.append("max_tokens = ?")
            params.append(max_tokens)
        if temperature is not None:
            updates.append("temperature = ?")
            params.append(temperature)
        if max_iterations is not None:
            updates.append("max_iterations = ?")
            params.append(max_iterations)
        if context_compression_enabled is not None:
            updates.append("context_compression_enabled = ?")
            params.append(context_compression_enabled)
        if context_compression_turns is not None:
            updates.append("context_compression_turns = ?")
            params.append(context_compression_turns)
        if context_compression_token_threshold is not None:
            updates.append("context_compression_token_threshold = ?")
            params.append(context_compression_token_threshold)
        if config_json is not None:
            updates.append("config_json = ?")
            params.append(json.dumps(config_json))

        if not updates:
            return False

        updates.append("updated_at = datetime('now', 'localtime')")

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE agent_defaults SET {', '.join(updates)}",
                tuple(params)
            )
            return cursor.rowcount > 0

    def get_enabled_models_for_selection(self) -> list[dict]:
        """Get all enabled models from enabled providers for selection.

        Returns list of models with provider info for dropdown selection.
        """
        with self.db._get_connection() as conn:
            rows = conn.execute(
                """SELECT
                    m.id as model_db_id,
                    m.model_id,
                    m.display_name as model_display_name,
                    p.id as provider_id,
                    p.name as provider_name,
                    p.display_name as provider_display_name
                FROM models m
                JOIN providers p ON m.provider_id = p.id
                WHERE m.enabled = 1 AND p.enabled = 1
                ORDER BY p.display_name ASC, m.display_name ASC"""
            ).fetchall()

            return [
                {
                    "value": f"{row['provider_id']}/{row['model_id']}",
                    "label": f"{row['provider_display_name']} - {row['model_display_name']}",
                    "providerId": row["provider_id"],
                    "providerName": row["provider_name"],
                    "providerDisplayName": row["provider_display_name"],
                    "modelId": row["model_id"],
                    "modelDbId": row["model_db_id"],
                    "modelDisplayName": row["model_display_name"],
                }
                for row in rows
            ]

    def _row_to_agent_defaults(self, row) -> AgentDefaultsRecord:
        """Convert database row to AgentDefaultsRecord."""
        return AgentDefaultsRecord(
            id=row["id"],
            default_provider_id=row["default_provider_id"],
            default_model_id=row["default_model_id"],
            workspace_path=row["workspace_path"] or "",
            max_tokens=row["max_tokens"] or 8192,
            temperature=row["temperature"] or 0.7,
            max_iterations=row["max_iterations"] or 20,
            context_compression_enabled=bool(row["context_compression_enabled"]),
            context_compression_turns=row["context_compression_turns"] or 10,
            context_compression_token_threshold=row["context_compression_token_threshold"] or 8000,
            llm_max_retries=row["llm_max_retries"] if "llm_max_retries" in row.keys() and row["llm_max_retries"] is not None else 3,
            llm_retry_base_delay=row["llm_retry_base_delay"] if "llm_retry_base_delay" in row.keys() and row["llm_retry_base_delay"] is not None else 1.0,
            llm_retry_max_delay=row["llm_retry_max_delay"] if "llm_retry_max_delay" in row.keys() and row["llm_retry_max_delay"] is not None else 30.0,
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# ========== Channel Config Repository ==========

@dataclass
class ChannelConfigRecord:
    """Channel config record data class."""
    id: int
    channel_name: str
    channel_type: str
    enabled: bool
    app_id: str
    app_secret: str
    encrypt_key: str
    verification_token: str
    allow_from: list[str]
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ChannelConfigRepository:
    """Repository for channel config database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_channel_config(self, channel_name: str) -> ChannelConfigRecord | None:
        """Get channel config by name."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM channel_configs WHERE channel_name = ?",
                (channel_name,)
            ).fetchone()
            return self._row_to_channel_config(row) if row else None

    def get_all_channel_configs(self) -> list[ChannelConfigRecord]:
        """Get all channel configs."""
        with self.db._get_connection() as conn:
            rows = conn.execute("SELECT * FROM channel_configs ORDER BY channel_name").fetchall()
            return [self._row_to_channel_config(row) for row in rows]

    def create_or_update_channel_config(
        self,
        channel_name: str,
        channel_type: str,
        enabled: bool = False,
        app_id: str = "",
        app_secret: str = "",
        encrypt_key: str = "",
        verification_token: str = "",
        allow_from: list[str] | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Create or update channel config."""
        allow_from = allow_from or []
        config_json = config_json or {}

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO channel_configs
                   (channel_name, channel_type, enabled, app_id, app_secret, encrypt_key,
                    verification_token, allow_from, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                   ON CONFLICT(channel_name) DO UPDATE SET
                   channel_type = excluded.channel_type,
                   enabled = excluded.enabled,
                   app_id = excluded.app_id,
                   app_secret = excluded.app_secret,
                   encrypt_key = excluded.encrypt_key,
                   verification_token = excluded.verification_token,
                   allow_from = excluded.allow_from,
                   config_json = excluded.config_json,
                   updated_at = excluded.updated_at""",
                (channel_name, channel_type, enabled, app_id, app_secret, encrypt_key,
                 verification_token, json.dumps(allow_from), json.dumps(config_json))
            )
            return cursor.rowcount > 0

    def delete_channel_config(self, channel_name: str) -> bool:
        """Delete channel config."""
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM channel_configs WHERE channel_name = ?",
                (channel_name,)
            )
            return cursor.rowcount > 0

    def _row_to_channel_config(self, row) -> ChannelConfigRecord:
        """Convert database row to ChannelConfigRecord."""
        return ChannelConfigRecord(
            id=row["id"],
            channel_name=row["channel_name"],
            channel_type=row["channel_type"],
            enabled=bool(row["enabled"]),
            app_id=row["app_id"] or "",
            app_secret=row["app_secret"] or "",
            encrypt_key=row["encrypt_key"] or "",
            verification_token=row["verification_token"] or "",
            allow_from=json.loads(row["allow_from"] or "[]"),
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# ========== Tool Config Repository ==========

@dataclass
class ToolConfigRecord:
    """Tool config record data class."""
    id: int
    tool_name: str
    enabled: bool
    timeout: int
    restrict_to_workspace: bool
    search_api_key: str
    search_max_results: int
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ToolConfigRepository:
    """Repository for tool config database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_tool_config(self, tool_name: str) -> ToolConfigRecord | None:
        """Get tool config by name."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tool_configs WHERE tool_name = ?",
                (tool_name,)
            ).fetchone()
            return self._row_to_tool_config(row) if row else None

    def get_all_tool_configs(self) -> list[ToolConfigRecord]:
        """Get all tool configs."""
        with self.db._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tool_configs ORDER BY tool_name").fetchall()
            return [self._row_to_tool_config(row) for row in rows]

    def create_or_update_tool_config(
        self,
        tool_name: str,
        enabled: bool = True,
        timeout: int = 60,
        restrict_to_workspace: bool = True,
        search_api_key: str = "",
        search_max_results: int = 5,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Create or update tool config."""
        config_json = config_json or {}

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO tool_configs
                   (tool_name, enabled, timeout, restrict_to_workspace, search_api_key,
                    search_max_results, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                   ON CONFLICT(tool_name) DO UPDATE SET
                   enabled = excluded.enabled,
                   timeout = excluded.timeout,
                   restrict_to_workspace = excluded.restrict_to_workspace,
                   search_api_key = excluded.search_api_key,
                   search_max_results = excluded.search_max_results,
                   config_json = excluded.config_json,
                   updated_at = excluded.updated_at""",
                (tool_name, enabled, timeout, restrict_to_workspace, search_api_key,
                 search_max_results, json.dumps(config_json))
            )
            return cursor.rowcount > 0

    def _row_to_tool_config(self, row) -> ToolConfigRecord:
        """Convert database row to ToolConfigRecord."""
        return ToolConfigRecord(
            id=row["id"],
            tool_name=row["tool_name"],
            enabled=bool(row["enabled"]),
            timeout=row["timeout"] or 60,
            restrict_to_workspace=bool(row["restrict_to_workspace"]),
            search_api_key=row["search_api_key"] or "",
            search_max_results=row["search_max_results"] or 5,
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# ========== Image Service Config Repository ==========

@dataclass
class ImageServiceConfigRecord:
    """Image service config record."""
    id: int
    config_type: str  # 'understanding' or 'generation'
    default_model_id: int | None
    default_size: str | None
    default_quality: str | None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ImageServiceConfigRepository:
    """Repository for image service config database operations.

    Image understanding and generation use models from enabled providers.
    This repository stores the default model selection.
    """

    # Provider types that support image understanding (基于图片中的8种类型)
    UNDERSTANDING_PROVIDER_TYPES = {'openai', 'openai-response', 'gemini', 'anthropic', 'azure-openai', 'new-api', 'cherryln', 'ollama'}
    # Provider types that support image generation
    GENERATION_PROVIDER_TYPES = {'openai', 'openai-response', 'azure-openai', 'new-api', 'cherryln'}

    # Default models for image understanding by provider type
    DEFAULT_UNDERSTANDING_MODELS = {
        'openai': 'gpt-4o',
        'openai-response': 'gpt-4o',
        'gemini': 'gemini-pro-vision',
        'anthropic': 'claude-3-opus-4-5',
        'azure-openai': 'gpt-4o',
        'new-api': 'gpt-4o',
        'cherryln': 'gpt-4o',
        'ollama': 'llava'
    }

    # Default models for image generation by provider type
    DEFAULT_GENERATION_MODELS = {
        'openai': 'dall-e-3',
        'openai-response': 'dall-e-3',
        'azure-openai': 'dall-e-3',
        'new-api': 'dall-e-3',
        'cherryln': 'dall-e-3'
    }

    def __init__(self, db: Database):
        self.db = db

    def get_config(self, config_type: str) -> ImageServiceConfigRecord | None:
        """Get image service config by type."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM image_service_config WHERE config_type = ?",
                (config_type,)
            ).fetchone()
            return self._row_to_config(row) if row else None

    def update_config(
        self,
        config_type: str,
        default_model_id: int | None = None,
        default_size: str | None = None,
        default_quality: str | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Update image service config."""
        updates = []
        params = []

        if default_model_id is not None:
            updates.append("default_model_id = ?")
            params.append(default_model_id)
        if default_size is not None:
            updates.append("default_size = ?")
            params.append(default_size)
        if default_quality is not None:
            updates.append("default_quality = ?")
            params.append(default_quality)
        if config_json is not None:
            updates.append("config_json = ?")
            params.append(json.dumps(config_json))

        if not updates:
            return False

        updates.append("updated_at = datetime('now', 'localtime')")
        params.append(config_type)

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE image_service_config SET {', '.join(updates)} WHERE config_type = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def get_available_models(self, config_type: str) -> list[dict]:
        """Get available models for image service from enabled providers.

        Returns models from providers that support the specified service type.
        Only models with supports_vision=1 or model_types containing 'vision' are returned.
        """
        if config_type == 'understanding':
            provider_types = self.UNDERSTANDING_PROVIDER_TYPES
        elif config_type == 'generation':
            provider_types = self.GENERATION_PROVIDER_TYPES
        else:
            return []

        # Build IN clause
        placeholders = ','.join('?' * len(provider_types))

        with self.db._get_connection() as conn:
            rows = conn.execute(
                f"""SELECT
                    m.id as model_db_id,
                    m.model_id,
                    m.display_name as model_display_name,
                    m.model_types,
                    m.supports_vision,
                    p.id as provider_id,
                    p.name as provider_name,
                    p.display_name as provider_display_name,
                    p.provider_type,
                    p.api_key,
                    p.api_host
                FROM models m
                JOIN providers p ON m.provider_id = p.id
                WHERE m.enabled = 1 AND p.enabled = 1 AND p.provider_type IN ({placeholders})
                  AND (m.supports_vision = 1 OR m.model_types LIKE '%vision%')
                ORDER BY p.display_name ASC, m.display_name ASC""",
                tuple(provider_types)
            ).fetchall()

            return [
                {
                    "value": row["model_db_id"],
                    "label": f"{row['provider_display_name']} - {row['model_display_name']}",
                    "providerId": row["provider_id"],
                    "providerName": row["provider_name"],
                    "providerDisplayName": row["provider_display_name"],
                    "providerType": row["provider_type"],
                    "modelId": row["model_id"],
                    "modelDbId": row["model_db_id"],
                    "modelDisplayName": row["model_display_name"],
                    "modelTypes": row["model_types"],
                    "supportsVision": bool(row["supports_vision"]),
                    "apiKey": row["api_key"],
                    "apiHost": row["api_host"],
                }
                for row in rows
            ]

    def get_default_model(self, config_type: str) -> dict | None:
        """Get default model for image service."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    m.id as model_db_id,
                    m.model_id,
                    m.display_name as model_display_name,
                    p.id as provider_id,
                    p.name as provider_name,
                    p.display_name as provider_display_name,
                    p.provider_type,
                    p.api_key,
                    p.api_host,
                    isc.default_size,
                    isc.default_quality
                FROM image_service_config isc
                JOIN models m ON isc.default_model_id = m.id
                JOIN providers p ON m.provider_id = p.id
                WHERE isc.config_type = ? AND m.enabled = 1 AND p.enabled = 1""",
                (config_type,)
            ).fetchone()

            if row:
                return {
                    "modelDbId": row["model_db_id"],
                    "modelId": row["model_id"],
                    "modelDisplayName": row["model_display_name"],
                    "providerId": row["provider_id"],
                    "providerName": row["provider_name"],
                    "providerDisplayName": row["provider_display_name"],
                    "providerType": row["provider_type"],
                    "apiKey": row["api_key"],
                    "apiHost": row["api_host"],
                    "defaultSize": row["default_size"] or "1024x1024",
                    "defaultQuality": row["default_quality"] or "standard",
                }
            return None

    def _row_to_config(self, row) -> ImageServiceConfigRecord:
        """Convert database row to ImageServiceConfigRecord."""
        return ImageServiceConfigRecord(
            id=row["id"],
            config_type=row["config_type"],
            default_model_id=row["default_model_id"],
            default_size=row["default_size"],
            default_quality=row["default_quality"],
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@dataclass
class TTSServiceConfigRecord:
    """TTS service config record."""
    id: int
    config_type: str
    default_model_id: int | None
    default_voice: str | None
    default_format: str | None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TTSServiceConfigRepository:
    """Repository for TTS service config database operations.

    TTS uses models from enabled providers that support audio.
    This repository stores the default model selection.
    """

    TTS_PROVIDER_TYPES = {'openai', 'openai-response', 'azure-openai', 'new-api', 'cherryln'}

    DEFAULT_TTS_MODELS = {
        'openai': 'tts-1',
        'openai-response': 'tts-1',
        'azure-openai': 'tts-1',
        'new-api': 'tts-1',
        'cherryln': 'tts-1'
    }

    def __init__(self, db: Database):
        self.db = db

    def get_config(self) -> TTSServiceConfigRecord | None:
        """Get TTS service config."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tts_service_config WHERE config_type = 'tts'"
            ).fetchone()
            return self._row_to_config(row) if row else None

    def update_config(
        self,
        default_model_id: int | None = None,
        default_voice: str | None = None,
        default_format: str | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> bool:
        """Update TTS service config."""
        updates = []
        params = []

        if default_model_id is not None:
            updates.append("default_model_id = ?")
            params.append(default_model_id)
        if default_voice is not None:
            updates.append("default_voice = ?")
            params.append(default_voice)
        if default_format is not None:
            updates.append("default_format = ?")
            params.append(default_format)
        if config_json is not None:
            updates.append("config_json = ?")
            params.append(json.dumps(config_json))

        if not updates:
            return False

        updates.append("updated_at = datetime('now', 'localtime')")
        params.append('tts')

        with self.db._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE tts_service_config SET {', '.join(updates)} WHERE config_type = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def get_available_models(self) -> list[dict]:
        """Get available models for TTS from enabled providers.

        Returns models from providers that support audio/TTS.
        """
        provider_types = self.TTS_PROVIDER_TYPES
        placeholders = ','.join('?' * len(provider_types))

        with self.db._get_connection() as conn:
            rows = conn.execute(
                f"""SELECT
                    m.id as model_db_id,
                    m.model_id,
                    m.display_name as model_display_name,
                    m.model_types,
                    p.id as provider_id,
                    p.name as provider_name,
                    p.display_name as provider_display_name,
                    p.provider_type,
                    p.api_key,
                    p.api_host
                FROM models m
                JOIN providers p ON m.provider_id = p.id
                WHERE m.enabled = 1 AND p.enabled = 1 AND p.provider_type IN ({placeholders})
                  AND (m.model_types LIKE '%audio%' OR m.model_types LIKE '%tts%' OR m.model_id LIKE '%tts%')
                ORDER BY p.display_name ASC, m.display_name ASC""",
                tuple(provider_types)
            ).fetchall()

            return [
                {
                    "value": row["model_db_id"],
                    "label": f"{row['provider_display_name']} - {row['model_display_name']}",
                    "providerId": row["provider_id"],
                    "providerName": row["provider_name"],
                    "providerDisplayName": row["provider_display_name"],
                    "providerType": row["provider_type"],
                    "modelId": row["model_id"],
                    "modelDbId": row["model_db_id"],
                    "modelDisplayName": row["model_display_name"],
                    "modelTypes": row["model_types"],
                    "apiKey": row["api_key"],
                    "apiHost": row["api_host"],
                }
                for row in rows
            ]

    def get_default_model(self) -> dict | None:
        """Get default model for TTS service."""
        with self.db._get_connection() as conn:
            row = conn.execute(
                """SELECT
                    m.id as model_db_id,
                    m.model_id,
                    m.display_name as model_display_name,
                    p.id as provider_id,
                    p.name as provider_name,
                    p.display_name as provider_display_name,
                    p.provider_type,
                    p.api_key,
                    p.api_host,
                    tsc.default_voice,
                    tsc.default_format
                FROM tts_service_config tsc
                JOIN models m ON tsc.default_model_id = m.id
                JOIN providers p ON m.provider_id = p.id
                WHERE tsc.config_type = 'tts' AND m.enabled = 1 AND p.enabled = 1"""
            ).fetchone()

            if row:
                return {
                    "modelDbId": row["model_db_id"],
                    "modelId": row["model_id"],
                    "modelDisplayName": row["model_display_name"],
                    "providerId": row["provider_id"],
                    "providerName": row["provider_name"],
                    "providerDisplayName": row["provider_display_name"],
                    "providerType": row["provider_type"],
                    "apiKey": row["api_key"],
                    "apiHost": row["api_host"],
                    "defaultVoice": row["default_voice"] or "alloy",
                    "defaultFormat": row["default_format"] or "mp3",
                }
            return None

    def _row_to_config(self, row) -> TTSServiceConfigRecord:
        """Convert database row to TTSServiceConfigRecord."""
        return TTSServiceConfigRecord(
            id=row["id"],
            config_type=row["config_type"],
            default_model_id=row["default_model_id"],
            default_voice=row["default_voice"],
            default_format=row["default_format"],
            config_json=json.loads(row["config_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
