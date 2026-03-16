"""Utility functions for backend."""

from backend.utils.helpers import (
    ensure_dir,
    init_workspace_path,
    get_workspace_path,
    get_data_path,
    get_extensions_path,
    get_plugins_path,
    get_memory_path,
    get_sessions_path,
)

# Backward compatibility alias
get_skills_path = get_extensions_path

__all__ = [
    "ensure_dir",
    "init_workspace_path",
    "get_workspace_path",
    "get_data_path",
    "get_extensions_path",
    "get_skills_path",  # Kept for backward compatibility
    "get_plugins_path",
    "get_memory_path",
    "get_sessions_path",
]
