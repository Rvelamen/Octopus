"""Extension loader for discovering and loading extensions."""

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from .base import Extension, SkillExtension, PluginExtension, LongTaskExtension

if TYPE_CHECKING:
    from backend.core.events.bus import MessageBus
    from backend.data import Database


class ExtensionLoader:
    """Loader for discovering and loading extensions.

    Extensions can be loaded from:
    1. workspace/extensions/ - User extensions (highest priority)
    2. octopus/extensions/builtin/ - Built-in extensions
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.extensions_dir = workspace / "extensions"
        self.builtin_dir = Path(__file__).parent / "builtin"

    def load_all(self) -> list[Extension]:
        """Load all available extensions.

        Returns:
            List of loaded extensions
        """
        extensions = []
        seen_names = set()

        # 1. Load from extensions/ (new format)
        if self.extensions_dir.exists():
            logger.info(f"Loading extensions from {self.extensions_dir}")
            for ext_dir in sorted(self.extensions_dir.iterdir()):
                if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                    ext = self._load_from_directory(ext_dir)
                    if ext and ext.name not in seen_names:
                        extensions.append(ext)
                        seen_names.add(ext.name)
                        logger.debug(f"Loaded extension: {ext.name} ({ext.type})")

        # 2. Load builtin extensions
        if self.builtin_dir.exists():
            logger.info(f"Loading builtin extensions from {self.builtin_dir}")
            for ext_dir in sorted(self.builtin_dir.iterdir()):
                if ext_dir.is_dir() and not ext_dir.name.startswith("."):
                    if ext_dir.name not in seen_names:
                        ext = self._load_from_directory(ext_dir)
                        if ext:
                            extensions.append(ext)
                            seen_names.add(ext.name)

        logger.info(f"Loaded {len(extensions)} extensions total")
        return extensions

    def _load_from_directory(self, directory: Path) -> Extension | None:
        """Load extension from directory.

        Args:
            directory: Extension directory

        Returns:
            Extension instance or None if invalid
        """
        # Try manifest.yaml first, then manifest.json
        manifest_file = directory / "manifest.yaml"
        if not manifest_file.exists():
            manifest_file = directory / "manifest.json"

        if manifest_file.exists():
            return self._load_new_format(directory, manifest_file)

        # Try to auto-detect type from directory contents
        return self._auto_detect_extension(directory)

    def _load_new_format(self, directory: Path, manifest_file: Path) -> Extension | None:
        """Load extension with manifest file.

        Args:
            directory: Extension directory
            manifest_file: Path to manifest file

        Returns:
            Extension instance
        """
        try:
            if manifest_file.suffix == ".json":
                manifest = json.loads(manifest_file.read_text())
            else:
                import yaml
                manifest = yaml.safe_load(manifest_file.read_text()) or {}
        except Exception as e:
            logger.error(f"Failed to load manifest from {directory}: {e}")
            return None

        name = manifest.get("name", directory.name)
        ext_type = manifest.get("type", "skill")

        # Create appropriate extension type
        # Note: worker type is treated as plugin (workers are implemented as plugins internally)
        if ext_type == "skill":
            return SkillExtension(name, directory, manifest)
        elif ext_type == "plugin":
            return PluginExtension(name, directory, manifest)
        elif ext_type == "longtask":
            return LongTaskExtension(name, directory, manifest)
        else:
            # Default to base Extension
            return Extension(name, directory, manifest)

    def _auto_detect_extension(self, directory: Path) -> Extension | None:
        """Auto-detect extension type from directory contents.

        Args:
            directory: Extension directory

        Returns:
            Extension instance or None
        """
        has_skill = (directory / "SKILL.md").exists()
        has_handler = (directory / "handler.py").exists()

        if has_handler:
            # Plugin extension (handler-based)
            manifest = {
                "name": directory.name,
                "type": "plugin",
                "description": f"Auto-detected plugin extension: {directory.name}",
                "plugin": {
                    "handler": f"extensions.{directory.name}.handler.Handler"
                }
            }
            return PluginExtension(directory.name, directory, manifest)
        elif has_skill:
            # Skill-only extension
            manifest = {
                "name": directory.name,
                "type": "skill",
                "description": f"Auto-detected skill extension: {directory.name}"
            }
            return SkillExtension(directory.name, directory, manifest)

        return None

    def load_skills(self) -> list[SkillExtension]:
        """Load only skill extensions.

        Returns:
            List of skill extensions
        """
        return [ext for ext in self.load_all() if isinstance(ext, SkillExtension)]

    def get_extension(self, name: str) -> Extension | None:
        """Get extension by name.

        Args:
            name: Extension name

        Returns:
            Extension instance or None
        """
        for ext in self.load_all():
            if ext.name == name:
                return ext
        return None



class SkillsLoader:
    """Loader for agent skills (using Extension system).

    This class provides a higher-level API for skill management,
    built on top of the Extension system.
    """

    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.extensions_dir = workspace / "extensions"
        self.builtin_dir = builtin_skills_dir or (Path(__file__).parent / "builtin")
        self._loader = ExtensionLoader(workspace)
        self._registry = None

    def _get_registry(self):
        """Lazy load registry."""
        if self._registry is None:
            from .registry import get_registry
            self._registry = get_registry()
            # Auto-load extensions on first access
            extensions = self._loader.load_all()
            for ext in extensions:
                if ext.name not in self._registry._extensions:
                    self._registry.register(ext)
        return self._registry

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """List all available skills.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts with 'name', 'path', 'source'.
        """
        skills = []
        for ext in self._get_registry().list_skills(filter_available=filter_unavailable):
            if not filter_unavailable or ext.check_requirements()[0]:
                skills.append({
                    "name": ext.name,
                    "path": str(ext.directory / "SKILL.md"),
                    "source": "builtin" if "builtin" in str(ext.directory) else "workspace"
                })
        return skills

    def load_skill(self, name: str) -> str | None:
        """Load a skill by name.

        Supports all extension types (skill, plugin) since they all
        have SKILL.md documentation.

        Args:
            name: Skill name (directory name).

        Returns:
            Skill content or None if not found.
        """
        # Try get_skill first for SkillExtension, then get for any extension type
        ext = self._get_registry().get_skill(name)
        if not ext:
            # Check plugins as well (they also have SKILL.md)
            ext = self._get_registry().get(name)
        if ext:
            return ext.load_documentation()
        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """Load specific skills for inclusion in agent context.

        Args:
            skill_names: List of skill names to load.

        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                parts.append(f"### Skill: {name}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self, exclude_types: list[str] | None = None) -> str:
        """Build a summary of all skills.

        Args:
            exclude_types: List of extension types to exclude (e.g., ["longtask"])

        Returns:
            XML-formatted skills summary.
        """
        return self._get_registry().build_skills_summary(exclude_types=exclude_types)

    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for skill in self._get_registry().list_skills(filter_available=True):
            if skill.type == "skill" and hasattr(skill, 'always_load') and skill.always_load:
                result.append(skill.name)
        return result

    def get_skill_metadata(self, name: str) -> dict | None:
        """Get metadata from a skill's frontmatter."""
        ext = self._get_registry().get(name)
        if ext:
            return ext._metadata
        return None

    def install_skill(self, source: str, name: str | None = None) -> dict:
        """Install a skill from source.

        Args:
            source: Git URL or local path
            name: Optional name for the skill

        Returns:
            Dict with installation result
        """
        try:
            if name is None:
                # Extract name from git URL
                name = source.split("/")[-1].replace(".git", "").replace("-", "_")

            target_dir = self.extensions_dir / name

            if target_dir.exists():
                return {"success": False, "error": f"Skill '{name}' already exists"}

            if source.startswith("http") or source.startswith("git@"):
                # Clone from git
                import subprocess
                result = subprocess.run(
                    ["git", "clone", source, str(target_dir)],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    return {"success": False, "error": result.stderr}
            elif os.path.isdir(source):
                # Copy from local directory
                shutil.copytree(source, target_dir)
            else:
                return {"success": False, "error": "Invalid source"}

            # Install dependencies if requirements.txt exists
            requirements_file = target_dir / "requirements.txt"
            if requirements_file.exists():
                try:
                    from .plugin_dependency import DependencyManager
                    dep_manager = DependencyManager(target_dir)
                    dep_manager.install(requirements_file)
                except Exception as e:
                    logger.warning(f"Failed to install dependencies for '{name}': {e}")

            # Reload extensions
            self._registry = None  # Clear cache
            self._get_registry()

            return {"success": True, "name": name, "path": str(target_dir)}

        except Exception as e:
            logger.error(f"Failed to install skill: {e}")
            return {"success": False, "error": str(e)}

    def uninstall_skill(self, name: str) -> dict:
        """Uninstall a skill.

        Args:
            name: Skill name

        Returns:
            Dict with uninstallation result
        """
        try:
            # Check if it's in workspace extensions
            target_dir = self.extensions_dir / name

            if not target_dir.exists():
                # Check if it's a builtin skill
                builtin_dir = self.builtin_dir / name
                if builtin_dir.exists():
                    return {"success": False, "error": "Cannot uninstall builtin skill"}
                return {"success": False, "error": f"Skill '{name}' not found"}

            # Remove directory
            shutil.rmtree(target_dir)

            # Unregister from registry
            self._get_registry().unregister(name)

            return {"success": True, "name": name}

        except Exception as e:
            logger.error(f"Failed to uninstall skill: {e}")
            return {"success": False, "error": str(e)}

    def update_skill(self, name: str) -> dict:
        """Update a skill from its git source.

        Args:
            name: Skill name

        Returns:
            Dict with update result
        """
        try:
            target_dir = self.extensions_dir / name

            if not target_dir.exists():
                return {"success": False, "error": f"Skill '{name}' not found"}

            # Check if it's a git repo
            git_dir = target_dir / ".git"
            if not git_dir.exists():
                return {"success": False, "error": "Skill was not installed from git"}

            # Pull latest
            import subprocess
            result = subprocess.run(
                ["git", "-C", str(target_dir), "pull"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {"success": False, "error": result.stderr}

            # Reload extensions
            self._registry = None  # Clear cache
            self._get_registry()

            return {"success": True, "name": name, "output": result.stdout}

        except Exception as e:
            logger.error(f"Failed to update skill: {e}")
            return {"success": False, "error": str(e)}

    def _get_skill_meta(self, name: str) -> dict:
        """Get octopus metadata for a skill."""
        ext = self._get_registry().get(name)
        if not ext:
            return {}
        return ext.manifest

    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True
