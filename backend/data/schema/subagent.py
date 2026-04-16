"""Subagent schema."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
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


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subagent_messages_instance ON subagent_messages(session_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subagent_messages_parent ON subagent_messages(parent_tool_call_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subagent_messages_subagent ON subagent_messages(subagent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subagents_name ON subagents(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subagents_provider ON subagents(provider_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subagents_model ON subagents(model_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_available_tools_name ON available_tools(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_available_extensions_name ON available_extensions(name)")


def seed_data(conn: sqlite3.Connection) -> None:
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
        ("kb_search", "KB Search", "Search the knowledge base for notes by path or title", "knowledge", 10),
        ("kb_timeline", "KB Timeline", "Preview a note's context before reading", "knowledge", 11),
        ("kb_read_note", "KB Read Note", "Read the full content of a knowledge base note", "knowledge", 12),
        ("kb_list_links", "KB List Links", "List bidirectional links for a given note path", "knowledge", 13),
        ("memory_write", "Memory Write", "Add, replace, or remove curated memory entries", "memory", 14),
        ("memory_search", "Memory Search", "Search observations and memory by keyword", "memory", 15),
        ("memory_read", "Memory Read", "Read curated memory or user profile", "memory", 16),
        ("memory_timeline", "Memory Timeline", "Get memory timeline for a session instance", "memory", 17),
    ]
    for name, display_name, description, category, sort_order in default_tools:
        conn.execute("""
            INSERT OR IGNORE INTO available_tools (name, display_name, description, category, enabled, sort_order)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (name, display_name, description, category, sort_order))
