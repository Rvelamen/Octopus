"""Core database module - unified SQLite database manager."""
import asyncio
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

from loguru import logger

from backend.data.schema import (
    apscheduler,
    mcp,
    session,
    provider,
    image,
    task,
    subagent,
    agent,
    channel,
    tool,
    token,
    observation,
)


class Database:
    """Unified SQLite database manager for all octopus data.

    Uses a single persistent synchronous connection protected by a threading.RLock
    to avoid the overhead of opening/closing connections on every query.
    Also exposes an async connection interface via aiosqlite for new code paths.
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
        self._lock = threading.RLock()
        self._async_lock: asyncio.Lock | None = None
        self._conn: sqlite3.Connection | None = None
        self._async_conn: Any | None = None
        self._init_database()

    def _open_sync_connection(self) -> sqlite3.Connection:
        """Open and configure a persistent SQLite connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception as e:
            logger.warning(f"Failed to enable WAL mode: {e}")
        return conn

    @contextmanager
    def _get_connection(self):
        """Get the shared synchronous database connection.

        Uses a persistent connection guarded by RLock to ensure serialised
        access in a multi-thread / multi-coroutine environment.
        """
        if self._conn is None:
            self._conn = self._open_sync_connection()
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    @asynccontextmanager
    async def connection(self):
        """Async context manager yielding an aiosqlite connection.

        Uses a single persistent async connection protected by asyncio.Lock.
        """
        import aiosqlite

        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        if self._async_conn is None:
            self._async_conn = await aiosqlite.connect(self.db_path)
            self._async_conn.row_factory = sqlite3.Row
            await self._async_conn.execute("PRAGMA foreign_keys = ON")
            try:
                await self._async_conn.execute("PRAGMA journal_mode=WAL")
            except Exception as e:
                logger.warning(f"Failed to enable WAL mode: {e}")
            await self._async_conn.commit()

        async with self._async_lock:
            try:
                yield self._async_conn
                await self._async_conn.commit()
            except Exception:
                await self._async_conn.rollback()
                raise

    def checkpoint(self, mode: str = "PASSIVE") -> None:
        """Run a WAL checkpoint to consolidate wal/shm files into the main db."""
        try:
            with self._get_connection() as conn:
                conn.execute(f"PRAGMA wal_checkpoint({mode})")
                logger.info(f"SQLite WAL checkpoint ({mode}) completed")
        except Exception as e:
            logger.warning(f"SQLite WAL checkpoint failed: {e}")

    def _init_database(self) -> None:
        """Initialize all database tables and run migrations."""
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
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except Exception as e:
                logger.warning(f"Failed to enable WAL mode during init: {e}")

            # Create tables in dependency order
            apscheduler.create_tables(conn)
            mcp.create_tables(conn)
            session.create_tables(conn)
            provider.create_tables(conn)
            image.create_tables(conn)
            task.create_tables(conn)
            subagent.create_tables(conn)
            agent.create_tables(conn)
            channel.create_tables(conn)
            tool.create_tables(conn)
            token.create_tables(conn)
            observation.create_tables(conn)

            # Create indexes
            apscheduler.create_indexes(conn)
            mcp.create_indexes(conn)
            session.create_indexes(conn)
            provider.create_indexes(conn)
            image.create_indexes(conn)
            task.create_indexes(conn)
            subagent.create_indexes(conn)
            agent.create_indexes(conn)
            channel.create_indexes(conn)
            tool.create_indexes(conn)
            token.create_indexes(conn)
            observation.create_indexes(conn)

            # Seed default data
            provider.seed_data(conn)
            channel.seed_data(conn)
            subagent.seed_data(conn)

        # Run yoyo migrations
        self._run_yoyo_migrations()

    def _run_yoyo_migrations(self) -> None:
        """Apply pending yoyo migrations."""
        try:
            from yoyo import get_backend, read_migrations
        except ImportError as e:
            # yoyo-migrations not installed, skip silently
            return
        except Exception as e:
            logger.warning(f"Yoyo import failed: {e}")
            return

        try:
            backend = get_backend(f"sqlite:///{self.db_path}")
            migrations_dir = Path(__file__).parent / "migrations"
            migrations = read_migrations(str(migrations_dir))
            to_apply = backend.to_apply(migrations)
            if to_apply:
                backend.apply_migrations(to_apply)
                logger.info(f"Applied {len(to_apply)} database migration(s)")
        except Exception as e:
            logger.warning(f"Yoyo migration run failed: {e}")

    def execute(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a query and return results."""
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchall()

    def execute_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute a query and return single result or None."""
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()
