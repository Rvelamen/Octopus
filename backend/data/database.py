"""Core database module - unified SQLite database manager."""
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
import time

from loguru import logger


class Database:
    """Unified SQLite database manager for all octopus data.
    
    Manages:
    - MCP servers and tools configuration
    - Session and message history
    - Tool usage statistics
    """
    
    def __init__(self, db_path: Path | None = None):
        """Initialize database.
        
        Args:
            db_path: Path to database file. Defaults to ~/.octopus/app.db
        """
        if db_path is None:
            from backend.utils.helpers import get_data_path
            db_path = get_data_path() / "app.db"
        
        self.db_path = Path(db_path)
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with row factory and foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints for cascade delete to work
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self) -> None:
        """Initialize all database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.db_path.exists() and not os.access(self.db_path, os.W_OK):
            logger.warning(f"Database file is not writable, attempting to fix permissions: {self.db_path}")
            try:
                os.chmod(self.db_path, 0o644)
            except Exception as e:
                logger.warning(f"Could not fix permissions: {e}")
                self.db_path = self.db_path.parent / f"app_{int(time.time())}.db"
                logger.warning(f"Using new database file: {self.db_path}")
        
        with self._get_connection() as conn:
            # ========== MCP Tables ==========
            
            # MCP servers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    protocol TEXT DEFAULT 'stdio',
                    enabled BOOLEAN DEFAULT 1,
                    auto_connect BOOLEAN DEFAULT 1,
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)
            
            # MCP tools table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    enabled BOOLEAN DEFAULT 1,
                    parameters_json TEXT DEFAULT '{}',
                    dependencies_json TEXT DEFAULT '[]',
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(server_id, name),
                    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
                )
            """)
            
            # MCP tool statistics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tool_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_id INTEGER NOT NULL UNIQUE,
                    use_count INTEGER DEFAULT 0,
                    last_used_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (tool_id) REFERENCES mcp_tools(id) ON DELETE CASCADE
                )
            """)
            
            # ========== Session Tables ==========
            
            # Main sessions table (channel:chat_id level)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    session_key TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    metadata TEXT DEFAULT '{}',
                    UNIQUE(channel, chat_id)
                )
            """)
            
            # Session instances table (multi-session support)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    instance_name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 0,
                    compressed_context TEXT DEFAULT '',
                    compressed_message_count INTEGER DEFAULT 0,
                    last_compressed_turn INTEGER DEFAULT 0,
                    compressed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            
            # Messages table (linked to session_instance)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_instance_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    metadata TEXT DEFAULT '{}',
                    is_compressed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
                )
            """)
            
            # ========== APScheduler Tables ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS apscheduler_jobs (
                    id TEXT NOT NULL PRIMARY KEY,
                    next_run_time FLOAT,
                    job_state BLOB NOT NULL
                )
            """)

            # ========== Async Task Tables ==========

            # Tasks table for long-running async tasks
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    parent_session TEXT NOT NULL,
                    parent_instance_id INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    input_params TEXT DEFAULT '{}',
                    progress_percent INTEGER DEFAULT 0,
                    progress_message TEXT,
                    current_step TEXT,
                    pending_auth TEXT,
                    auth_payload TEXT,
                    auth_timeout_at TIMESTAMP,
                    result_summary TEXT,
                    result_details TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    started_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    completed_at TIMESTAMP,
                    FOREIGN KEY (parent_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
                )
            """)

            # Task events log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            """)

            # ========== Subagent Tables ==========

            # Subagent messages table (独立存储 subagent 的消息)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subagent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_instance_id INTEGER NOT NULL,
                    subagent_id TEXT NOT NULL,
                    parent_tool_call_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'subagent_tool_call',
                    tool_call_id TEXT,
                    timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
                )
            """)

            # ========== Indexes ==========
            
            # MCP indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcp_servers_name ON mcp_servers(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON mcp_tools(server_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcp_tools_name ON mcp_tools(name)
            """)
            
            # Session indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(session_key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_session ON session_instances(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_active ON session_instances(session_id, is_active)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_instance ON messages(session_instance_id)
            """)

            # Task indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(parent_session)
            """)

            # Subagent indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subagent_messages_instance ON subagent_messages(session_instance_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subagent_messages_parent ON subagent_messages(parent_tool_call_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subagent_messages_subagent ON subagent_messages(subagent_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_instance ON tasks(parent_instance_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_pending_auth ON tasks(pending_auth, status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id)
            """)

            # User uploaded/generated images table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_instance_id INTEGER,
                    image_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    mime_type TEXT DEFAULT 'image/png',
                    file_size INTEGER DEFAULT 0,
                    width INTEGER,
                    height INTEGER,
                    description TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (session_instance_id) REFERENCES session_instances(id) ON DELETE CASCADE
                )
            """)

            # ========== Image Indexes ==========

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_session ON images(session_instance_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_type ON images(image_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_session ON images(session_instance_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_images_type ON images(image_type)
            """)

            # ========== LLM Provider Tables ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    api_key TEXT DEFAULT '',
                    api_host TEXT DEFAULT '',
                    api_version TEXT DEFAULT '',
                    enabled BOOLEAN DEFAULT 1,
                    is_system BOOLEAN DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id INTEGER NOT NULL,
                    model_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    model_type TEXT DEFAULT 'chat',
                    model_types TEXT DEFAULT '["chat"]',
                    group_name TEXT DEFAULT 'Chat Models',
                    max_tokens INTEGER DEFAULT 4096,
                    context_window INTEGER DEFAULT 128000,
                    supports_vision BOOLEAN DEFAULT 0,
                    supports_function_calling BOOLEAN DEFAULT 1,
                    supports_streaming BOOLEAN DEFAULT 1,
                    enabled BOOLEAN DEFAULT 1,
                    is_default BOOLEAN DEFAULT 0,
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
                    UNIQUE(provider_id, model_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT,
                    value_type TEXT DEFAULT 'string',
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            # ========== Image Service Config Tables ==========
            # Store default model IDs for image understanding and generation
            # Models are selected from enabled providers' models

            conn.execute("""
                CREATE TABLE IF NOT EXISTS image_service_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_type TEXT UNIQUE NOT NULL,
                    default_model_id INTEGER,
                    default_size TEXT DEFAULT '1024x1024',
                    default_quality TEXT DEFAULT 'standard',
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (default_model_id) REFERENCES models(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_image_service_config_type ON image_service_config(config_type)
            """)

            conn.execute("""
                INSERT OR IGNORE INTO image_service_config (config_type, default_model_id, default_size, default_quality)
                VALUES ('understanding', NULL, NULL, NULL)
            """)
            conn.execute("""
                INSERT OR IGNORE INTO image_service_config (config_type, default_model_id, default_size, default_quality)
                VALUES ('generation', NULL, '1024x1024', 'standard')
            """)

            # ========== TTS Service Config Table ==========
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tts_service_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_type TEXT UNIQUE NOT NULL,
                    default_model_id INTEGER,
                    default_voice TEXT DEFAULT 'alloy',
                    default_format TEXT DEFAULT 'mp3',
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (default_model_id) REFERENCES models(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                INSERT OR IGNORE INTO tts_service_config (config_type, default_model_id, default_voice, default_format)
                VALUES ('tts', NULL, 'alloy', 'mp3')
            """)

            # ========== Provider & Model Indexes ==========

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_providers_type ON providers(provider_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_providers_enabled ON providers(enabled)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_models_enabled ON models(enabled)
            """)

            # ========== Agent Defaults Table ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_defaults (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    default_provider_id INTEGER,
                    default_model_id INTEGER,
                    workspace_path TEXT DEFAULT '',
                    max_tokens INTEGER DEFAULT 8192,
                    temperature REAL DEFAULT 0.7,
                    max_iterations INTEGER DEFAULT 20,
                    context_compression_enabled BOOLEAN DEFAULT 0,
                    context_compression_turns INTEGER DEFAULT 10,
                    context_compression_token_threshold INTEGER DEFAULT 200000,
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (default_provider_id) REFERENCES providers(id) ON DELETE SET NULL,
                    FOREIGN KEY (default_model_id) REFERENCES models(id) ON DELETE SET NULL
                )
            """)

            # ========== Agent Defaults Indexes ==========

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_defaults_provider ON agent_defaults(default_provider_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_defaults_model ON agent_defaults(default_model_id)
            """)

            # ========== Channel Configs Table ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT UNIQUE NOT NULL,
                    channel_type TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 0,
                    app_id TEXT DEFAULT '',
                    app_secret TEXT DEFAULT '',
                    encrypt_key TEXT DEFAULT '',
                    verification_token TEXT DEFAULT '',
                    allow_from TEXT DEFAULT '[]',
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_configs_name ON channel_configs(channel_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_configs_enabled ON channel_configs(enabled)
            """)

            # ========== Tool Configs Table ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT UNIQUE NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    timeout INTEGER DEFAULT 60,
                    restrict_to_workspace BOOLEAN DEFAULT 1,
                    search_api_key TEXT DEFAULT '',
                    search_max_results INTEGER DEFAULT 5,
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_configs_name ON tool_configs(tool_name)
            """)

            # ========== Token Usage Tables ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_instance_id INTEGER,
                    provider_name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    cached_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    request_type TEXT DEFAULT 'chat',
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT,
                    provider_name TEXT,
                    model_id TEXT,
                    total_prompt_tokens INTEGER DEFAULT 0,
                    total_completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    request_count INTEGER DEFAULT 0,
                    date_date TEXT,
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(scope_type, scope_id, provider_name, model_id, date_date)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_instance ON token_usage(session_instance_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_summary_scope ON token_usage_summary(scope_type, scope_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_summary_date ON token_usage_summary(date_date)
            """)

            # ========== Subagent Tables ==========

            conn.execute("""
                CREATE TABLE IF NOT EXISTS subagents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    provider_id INTEGER,
                    model_id INTEGER,
                    tools TEXT DEFAULT '[]',
                    extensions TEXT DEFAULT '[]',
                    max_iterations INTEGER DEFAULT 30,
                    temperature REAL DEFAULT 0.7,
                    system_prompt TEXT DEFAULT '',
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE SET NULL,
                    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE SET NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS available_tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'filesystem',
                    enabled BOOLEAN DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS available_extensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    extension_type TEXT DEFAULT 'skill',
                    enabled BOOLEAN DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subagents_name ON subagents(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subagents_provider ON subagents(provider_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subagents_model ON subagents(model_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_available_tools_name ON available_tools(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_available_extensions_name ON available_extensions(name)
            """)

            # ========== Default Data ==========

            # Insert default feishu channel config
            conn.execute("""
                INSERT OR IGNORE INTO channel_configs 
                (channel_name, channel_type, enabled, app_id, app_secret, encrypt_key, verification_token, allow_from, config_json)
                VALUES ('feishu', 'feishu', 0, '', '', '', '', '[]', '{}')
            """)

            # Insert default wechat channel config
            conn.execute("""
                INSERT OR IGNORE INTO channel_configs 
                (channel_name, channel_type, enabled, app_id, app_secret, encrypt_key, verification_token, allow_from, config_json)
                VALUES ('wechat', 'wechat', 0, '', '', '', '', '[]', '{}')
            """)

            # Insert default available tools
            default_tools = [
                ("read", "Read File", "Read file contents from the filesystem", "filesystem", 1),
                ("write", "Write File", "Write content to a file", "filesystem", 2),
                ("edit", "Edit File", "Edit file using search and replace", "filesystem", 3),
                ("list", "List Directory", "List directory contents", "filesystem", 4),
                ("glob", "Glob Pattern", "Find files matching a pattern", "filesystem", 5),
                ("grep", "Grep Search", "Search for patterns in files", "filesystem", 6),
                ("exec", "Execute Command", "Run shell commands", "shell", 7),
                ("action", "Action", "Perform actions and operations", "action", 8),
                ("message", "Message", "Send messages to users", "communication", 9),
            ]
            for name, display_name, description, category, sort_order in default_tools:
                conn.execute("""
                    INSERT OR IGNORE INTO available_tools (name, display_name, description, category, enabled, sort_order)
                    VALUES (?, ?, ?, ?, 1, ?)
                """, (name, display_name, description, category, sort_order))

            # Run migrations after all tables are created
            self._run_migrations(conn)

            # logger.info(f"Database initialized: {self.db_path}")
    
    def _run_migrations(self, conn) -> None:
        """Run database migrations."""
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='models'"
            )
            if not cursor.fetchone():
                return
            
            cursor = conn.execute("PRAGMA table_info(models)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if columns and 'model_types' not in columns:
                conn.execute("ALTER TABLE models ADD COLUMN model_types TEXT DEFAULT '[\"chat\"]'")
                logger.info("Migration: Added model_types column to models table")
            
            # Migration for session_instances table - compression fields
            cursor = conn.execute("PRAGMA table_info(session_instances)")
            instance_columns = [row[1] for row in cursor.fetchall()]
            
            if instance_columns:
                if 'compressed_context' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN compressed_context TEXT DEFAULT ''")
                    logger.info("Migration: Added compressed_context column to session_instances table")
                
                if 'compressed_message_count' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN compressed_message_count INTEGER DEFAULT 0")
                    logger.info("Migration: Added compressed_message_count column to session_instances table")
                
                if 'last_compressed_turn' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN last_compressed_turn INTEGER DEFAULT 0")
                    logger.info("Migration: Added last_compressed_turn column to session_instances table")
                
                if 'compressed_at' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN compressed_at TIMESTAMP")
                    logger.info("Migration: Added compressed_at column to session_instances table")
            
            # Migration for messages table - is_compressed field
            cursor = conn.execute("PRAGMA table_info(messages)")
            message_columns = [row[1] for row in cursor.fetchall()]
            
            if message_columns and 'is_compressed' not in message_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN is_compressed BOOLEAN DEFAULT 0")
                logger.info("Migration: Added is_compressed column to messages table")
            
            # Migration for token_usage table - cached_tokens field
            cursor = conn.execute("PRAGMA table_info(token_usage)")
            token_usage_columns = [row[1] for row in cursor.fetchall()]

            if token_usage_columns and 'cached_tokens' not in token_usage_columns:
                conn.execute("ALTER TABLE token_usage ADD COLUMN cached_tokens INTEGER DEFAULT 0")
                logger.info("Migration: Added cached_tokens column to token_usage table")

            # Migration for token_usage table - remove ON DELETE CASCADE foreign key
            fk_cursor = conn.execute("PRAGMA foreign_key_list(token_usage)")
            has_fk = any(row for row in fk_cursor.fetchall())
            if has_fk:
                conn.execute("ALTER TABLE token_usage RENAME TO token_usage_old")
                conn.execute("""
                    CREATE TABLE token_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_instance_id INTEGER,
                        provider_name TEXT NOT NULL,
                        model_id TEXT NOT NULL,
                        prompt_tokens INTEGER DEFAULT 0,
                        completion_tokens INTEGER DEFAULT 0,
                        cached_tokens INTEGER DEFAULT 0,
                        total_tokens INTEGER DEFAULT 0,
                        request_type TEXT DEFAULT 'chat',
                        created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                    )
                """)
                conn.execute("""
                    INSERT INTO token_usage
                        (id, session_instance_id, provider_name, model_id,
                         prompt_tokens, completion_tokens, cached_tokens, total_tokens,
                         request_type, created_at)
                    SELECT
                        id, session_instance_id, provider_name, model_id,
                        prompt_tokens, completion_tokens,
                        COALESCE(cached_tokens, 0) as cached_tokens,
                        total_tokens, request_type, created_at
                    FROM token_usage_old
                """)
                conn.execute("DROP TABLE token_usage_old")
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_instance ON token_usage(session_instance_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider_name)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at)
                """)
                logger.info("Migration: Rebuilt token_usage table without foreign key cascade")

            # Migration for agent_defaults table - token threshold field
            cursor = conn.execute("PRAGMA table_info(agent_defaults)")
            agent_columns = [row[1] for row in cursor.fetchall()]

            if agent_columns and 'context_compression_token_threshold' not in agent_columns:
                conn.execute("ALTER TABLE agent_defaults ADD COLUMN context_compression_token_threshold INTEGER DEFAULT 200000")
                logger.info("Migration: Added context_compression_token_threshold column to agent_defaults table")

            if agent_columns and 'llm_max_retries' not in agent_columns:
                conn.execute("ALTER TABLE agent_defaults ADD COLUMN llm_max_retries INTEGER DEFAULT 3")
                logger.info("Migration: Added llm_max_retries column to agent_defaults table")
            
            if agent_columns and 'llm_retry_base_delay' not in agent_columns:
                conn.execute("ALTER TABLE agent_defaults ADD COLUMN llm_retry_base_delay REAL DEFAULT 1.0")
                logger.info("Migration: Added llm_retry_base_delay column to agent_defaults table")
            
            if agent_columns and 'llm_retry_max_delay' not in agent_columns:
                conn.execute("ALTER TABLE agent_defaults ADD COLUMN llm_retry_max_delay REAL DEFAULT 30.0")
                logger.info("Migration: Added llm_retry_max_delay column to agent_defaults table")
            
            # Migration for session_instances table - TTS fields
            cursor = conn.execute("PRAGMA table_info(session_instances)")
            instance_columns = [row[1] for row in cursor.fetchall()]
            
            if instance_columns:
                if 'tts_enabled' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN tts_enabled BOOLEAN DEFAULT 0")
                    logger.info("Migration: Added tts_enabled column to session_instances table")
                
                if 'tts_config' not in instance_columns:
                    conn.execute("ALTER TABLE session_instances ADD COLUMN tts_config TEXT DEFAULT '{}'")
                    logger.info("Migration: Added tts_config column to session_instances table")
            
        except Exception as e:
            logger.warning(f"Migration failed (may be expected): {e}")
    
    def execute(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of row results
        """
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchall()
    
    def execute_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute a query and return single result or None.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Single row or None
        """
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()
