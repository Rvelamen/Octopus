"""Shared temporary workspace for book-world public boundary tests."""

from pathlib import Path

import pytest

from backend.services.knowledge_migrations import run_knowledge_index_migrations
from backend.services.library_engine import LibraryEngine


@pytest.fixture
def book_library(tmp_path: Path):
    run_knowledge_index_migrations(tmp_path / "knowledge" / ".knowledge_index.db")
    engine = LibraryEngine(str(tmp_path))
    yield engine
    engine.db.close()
    LibraryEngine._instances.pop(str(tmp_path.resolve()), None)
