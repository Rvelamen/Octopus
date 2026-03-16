"""Utility functions for backend."""

import threading
from pathlib import Path
from datetime import datetime


# Global workspace configuration
_workspace_config = {
    "path": None,  # Will be set during initialization
    "lock": threading.Lock(),
}


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_workspace_path(workspace: str | None = None) -> Path:
    """
    Initialize the global workspace path.
    This should be called once during application startup.
    
    Args:
        workspace: Optional workspace path. If not provided, defaults to ~/.octopus/workspace.
    
    Returns:
        The initialized workspace path.
    """
    with _workspace_config["lock"]:
        if workspace:
            path = Path(workspace).expanduser()
        else:
            path = Path.home() / ".octopus" / "workspace"
        
        _workspace_config["path"] = ensure_dir(path)
        return _workspace_config["path"]


def _find_project_workspace() -> Path | None:
    """Find workspace in project directory.

    Walks up from current file to find workspace directory.
    Returns None if not found.
    """
    # Start from this file's location (octopus/utils/helpers.py)
    current = Path(__file__).resolve().parent

    # Walk up looking for workspace directory
    for parent in [current, *current.parents]:
        workspace = parent / "workspace"
        if workspace.exists() and workspace.is_dir():
            # Check if it contains expected subdirectories
            if (workspace / "system").exists() or (workspace / "extensions").exists():
                return workspace

    return None


def get_workspace_path() -> Path:
    """
    Get the current workspace path.
    Must call init_workspace_path() first during application startup.

    Returns:
        The configured workspace path.

    Raises:
        RuntimeError: If workspace has not been initialized.
    """
    with _workspace_config["lock"]:
        if _workspace_config["path"] is None:
            # Try to find project workspace first
            project_workspace = _find_project_workspace()
            if project_workspace:
                _workspace_config["path"] = ensure_dir(project_workspace)
            else:
                # Fall back to default user directory
                path = Path.home() / ".octopus" / "workspace"
                _workspace_config["path"] = ensure_dir(path)
        return _workspace_config["path"]


def get_data_path() -> Path:
    """Get the octopus data directory (~/.octopus)."""
    return ensure_dir(Path.home() / ".octopus")


def get_sessions_path() -> Path:
    """Get the sessions storage directory."""
    return ensure_dir(get_data_path() / "sessions")


def get_memory_path() -> Path:
    """Get the memory directory within the workspace."""
    return ensure_dir(get_workspace_path() / "memory")


def get_extensions_path() -> Path:
    """Get the extensions directory within the workspace."""
    return ensure_dir(get_workspace_path() / "extensions")


def get_plugins_path() -> Path:
    """Get the plugins directory within the workspace."""
    return ensure_dir(get_workspace_path() / "plugins")


def today_date() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def truncate_string(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate a string to max length, adding suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix


def safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    # Replace unsafe characters
    unsafe = '<>:"/\\|?*'
    for char in unsafe:
        name = name.replace(char, "_")
    return name.strip()


def parse_session_key(key: str) -> tuple[str, str]:
    """
    Parse a session key into channel and chat_id.
    
    Args:
        key: Session key in format "channel:chat_id"
    
    Returns:
        Tuple of (channel, chat_id)
    """
    parts = key.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid session key: {key}")
    return parts[0], parts[1]
