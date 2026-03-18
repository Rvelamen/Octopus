"""Workspace template service for initializing and updating workspace directories."""

import shutil
from pathlib import Path
from typing import Callable

from loguru import logger


class WorkspaceTemplateService:
    """Service for managing workspace template initialization and updates.

    Handles:
    1. First-time initialization: copies template files to the workspace
    2. Workspace path changes: copies template files to the new workspace
    """

    TEMPLATE_FILES = [
        "AGENTS.md",
        "BOOTSTRAP.md",
        "IDENTITY.md",
        "SOUL.md",
        "USER.md",
    ]

    TEMPLATE_DIRS = [
        "agents",
        "avatars",
        "extensions",
        "memory",
    ]

    def __init__(self, template_base_path: Path | None = None):
        """Initialize the workspace template service.

        Args:
            template_base_path: Base path for template files. Defaults to backend/templates/workspace
        """
        if template_base_path is None:
            template_base_path = Path(__file__).parent.parent / "templates" / "workspace"
        self.template_base_path = Path(template_base_path)

    def get_template_path(self) -> Path:
        """Get the template base path."""
        return self.template_base_path

    def copy_to_workspace(self, workspace_path: Path, skip_existing: bool = True) -> bool:
        """Copy template files to a workspace directory.

        Args:
            workspace_path: Target workspace path.
            skip_existing: If True, skip files that already exist in the workspace.

        Returns:
            True if successful, False otherwise.
        """
        try:
            workspace = Path(workspace_path)
            workspace.mkdir(parents=True, exist_ok=True)

            for dirname in self.TEMPLATE_DIRS:
                target_dir = workspace / dirname
                target_dir.mkdir(parents=True, exist_ok=True)

            for filename in self.TEMPLATE_FILES:
                target_file = workspace / filename
                if skip_existing and target_file.exists():
                    logger.debug(f"Skipping existing file: {target_file}")
                    continue

                source_file = self.template_base_path / filename
                if source_file.exists():
                    shutil.copy2(source_file, target_file)
                    logger.info(f"Copied template file: {filename} -> {target_file}")

            agent_dirs = ["code-worker", "researcher"]
            for agent_name in agent_dirs:
                agent_dir = workspace / "agents" / agent_name
                agent_dir.mkdir(parents=True, exist_ok=True)
                soul_file = agent_dir / "SOUL.md"
                if skip_existing and soul_file.exists():
                    continue
                source_file = self.template_base_path / "agents" / agent_name / "SOUL.md"
                if source_file.exists():
                    shutil.copy2(source_file, soul_file)
                    logger.info(f"Copied agent SOUL.md: {agent_name}/SOUL.md")

            logger.info(f"Template files copied to workspace: {workspace}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy template files to workspace: {e}")
            return False

    def setup_workspace(
        self,
        workspace_path: Path,
        on_progress: Callable[[str, int], None] | None = None,
    ) -> bool:
        """Setup workspace with template files, showing progress.

        Args:
            workspace_path: Target workspace path.
            on_progress: Optional callback for progress updates (message, percentage).

        Returns:
            True if successful, False otherwise.
        """
        try:
            workspace = Path(workspace_path)
            workspace.mkdir(parents=True, exist_ok=True)

            all_items = list(self.TEMPLATE_DIRS) + list(self.TEMPLATE_FILES) + ["agents/code-worker", "agents/researcher"]
            total_steps = len(all_items)
            current_step = 0

            for dirname in self.TEMPLATE_DIRS:
                target_dir = workspace / dirname
                target_dir.mkdir(parents=True, exist_ok=True)
                current_step += 1
                if on_progress:
                    on_progress(f"Creating directory: {dirname}", int(current_step / total_steps * 100))

            for filename in self.TEMPLATE_FILES:
                target_file = workspace / filename
                if target_file.exists():
                    current_step += 1
                    if on_progress:
                        on_progress(f"Skipping existing: {filename}", int(current_step / total_steps * 100))
                    continue

                source_file = self.template_base_path / filename
                if source_file.exists():
                    shutil.copy2(source_file, target_file)
                current_step += 1
                if on_progress:
                    on_progress(f"Creating file: {filename}", int(current_step / total_steps * 100))

            agent_dirs = ["code-worker", "researcher"]
            for agent_name in agent_dirs:
                agent_dir = workspace / "agents" / agent_name
                agent_dir.mkdir(parents=True, exist_ok=True)
                soul_file = agent_dir / "SOUL.md"
                if soul_file.exists():
                    current_step += 1
                    if on_progress:
                        on_progress(f"Skipping existing agent: {agent_name}", int(current_step / total_steps * 100))
                    continue

                source_file = self.template_base_path / "agents" / agent_name / "SOUL.md"
                if source_file.exists():
                    shutil.copy2(source_file, soul_file)
                current_step += 1
                if on_progress:
                    on_progress(f"Creating agent: {agent_name}", int(current_step / total_steps * 100))

            logger.info(f"Workspace setup completed: {workspace}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup workspace: {e}")
            return False


_workspace_template_service: WorkspaceTemplateService | None = None


def get_workspace_template_service() -> WorkspaceTemplateService:
    """Get the global workspace template service instance."""
    global _workspace_template_service
    if _workspace_template_service is None:
        _workspace_template_service = WorkspaceTemplateService()
    return _workspace_template_service


def setup_workspace_from_template(workspace_path: Path) -> bool:
    """Setup a workspace using the template files."""
    service = get_workspace_template_service()
    return service.copy_to_workspace(workspace_path)
