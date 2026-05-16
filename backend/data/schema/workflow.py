"""Workflow schema - the definitive data model for visual workflow orchestration."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    # ── 定义层：工作流模板 ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'draft',
            current_version INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_versions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            definition TEXT NOT NULL DEFAULT '{}',
            status TEXT DEFAULT 'draft',
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            UNIQUE(workflow_id, version)
        )
    """)

    # ── 定义层：节点与边（从 definition JSON 中独立出来，方便查询和索引） ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_nodes (
            id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL REFERENCES workflow_versions(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            label TEXT NOT NULL,
            position_x REAL DEFAULT 0,
            position_y REAL DEFAULT 0,
            width REAL DEFAULT 200,
            height REAL DEFAULT 80,
            config TEXT NOT NULL DEFAULT '{}',
            timeout_seconds INTEGER DEFAULT 300,
            max_retries INTEGER DEFAULT 0,
            retry_delay_seconds INTEGER DEFAULT 5,
            parent_id TEXT REFERENCES workflow_nodes(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_edges (
            id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL REFERENCES workflow_versions(id) ON DELETE CASCADE,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            label TEXT DEFAULT '',
            condition TEXT DEFAULT '',
            source_handle TEXT DEFAULT '',
            target_handle TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ── 配置层：变量与触发器 ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_variables (
            id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL REFERENCES workflow_versions(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            default_value TEXT DEFAULT '',
            description TEXT DEFAULT '',
            required BOOLEAN DEFAULT 1,
            is_input BOOLEAN DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            UNIQUE(version_id, name)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_triggers (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            trigger_type TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ── 运行时层：执行实例 ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL REFERENCES workflows(id),
            version_id TEXT NOT NULL REFERENCES workflow_versions(id),
            trigger_type TEXT NOT NULL,
            trigger_config TEXT DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            input_variables TEXT DEFAULT '{}',
            output_result TEXT DEFAULT '{}',
            error_message TEXT,
            current_node_id TEXT,
            session_instance_id INTEGER,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_run_nodes (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
            node_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            input_data TEXT DEFAULT '{}',
            output_data TEXT DEFAULT '{}',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            logs TEXT DEFAULT '[]'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_run_variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value TEXT,
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            UNIQUE(run_id, name)
        )
    """)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Migrate existing tables by adding columns that were added after initial creation."""
    cursor = conn.execute("PRAGMA table_info(workflow_runs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "session_instance_id" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN session_instance_id INTEGER")

    cursor = conn.execute("PRAGMA table_info(workflow_run_nodes)")
    existing_run_node_cols = {row[1] for row in cursor.fetchall()}
    if "created_at" not in existing_run_node_cols:
        conn.execute("ALTER TABLE workflow_run_nodes ADD COLUMN created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))")

    cursor = conn.execute("PRAGMA table_info(workflow_nodes)")
    existing_node_cols = {row[1] for row in cursor.fetchall()}
    if "parent_id" not in existing_node_cols:
        conn.execute("ALTER TABLE workflow_nodes ADD COLUMN parent_id TEXT REFERENCES workflow_nodes(id) ON DELETE SET NULL")

    # Migrate id column from INTEGER to TEXT (store.py uses UUID strings)
    col_info = {row[1]: row for row in conn.execute("PRAGMA table_info(workflow_run_nodes)").fetchall()}
    id_col = col_info.get("id")
    if id_col and id_col[2].upper() == "INTEGER":
        conn.execute("""
            CREATE TABLE workflow_run_nodes_new (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                input_data TEXT DEFAULT '{}',
                output_data TEXT DEFAULT '{}',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                logs TEXT DEFAULT '[]'
            )
        """)
        conn.execute("""
            INSERT INTO workflow_run_nodes_new (id, run_id, node_id, status, input_data, output_data, started_at, completed_at, created_at, error_message, retry_count, logs)
            SELECT id, run_id, node_id, status, input_data, output_data, started_at, completed_at, COALESCE(created_at, datetime('now', 'localtime')), error_message, retry_count, logs FROM workflow_run_nodes
        """)
        conn.execute("DROP TABLE workflow_run_nodes")
        conn.execute("ALTER TABLE workflow_run_nodes_new RENAME TO workflow_run_nodes")


def create_indexes(conn: sqlite3.Connection) -> None:
    _ensure_columns(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_versions_wf ON workflow_versions(workflow_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_nodes_version ON workflow_nodes(version_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_edges_version ON workflow_edges(version_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_variables_version ON workflow_variables(version_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_triggers_wf ON workflow_triggers(workflow_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_wf ON workflow_runs(workflow_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_session ON workflow_runs(session_instance_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_run_nodes_run ON workflow_run_nodes(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_run_nodes_node ON workflow_run_nodes(node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_run_vars_run ON workflow_run_variables(run_id)")


def seed_data(conn: sqlite3.Connection) -> None:
    pass
