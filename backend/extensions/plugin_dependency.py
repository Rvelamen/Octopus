"""Dependency management for plugins with isolated installation."""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from loguru import logger


class DependencyManager:
    """
    Manage plugin dependencies with isolated installation.
    
    Each plugin's dependencies are installed to a private deps/ directory
    to avoid conflicts with the main environment or other plugins.
    """
    
    # Packages that are provided by the main environment
    # Plugins should not install these to avoid conflicts
    SYSTEM_PACKAGES = {
        # Standard library
        "asyncio", "typing", "pathlib", "json", "re", "datetime", 
        "collections", "functools", "itertools", "os", "sys",
        "abc", "dataclasses", "types", "inspect", "importlib",
        # Main project dependencies (commonly used)
        "loguru", "pydantic", 
    }
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.deps_dir = plugin_dir / "deps"
        self._hash_file = plugin_dir / ".deps_hash"
    
    def _get_requirements_hash(self, requirements_file: Path) -> str:
        """Calculate hash of requirements file content."""
        content = requirements_file.read_text()
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_up_to_date(self, requirements_file: Path) -> bool:
        """Check if dependencies are already installed and up to date."""
        if not self._hash_file.exists():
            return False
        
        if not self.deps_dir.exists():
            return False
        
        current_hash = self._get_requirements_hash(requirements_file)
        stored_hash = self._hash_file.read_text().strip()
        
        return current_hash == stored_hash
    
    def _save_hash(self, requirements_file: Path) -> None:
        """Save the hash of installed requirements."""
        current_hash = self._get_requirements_hash(requirements_file)
        self._hash_file.write_text(current_hash)
    
    async def install(self, requirements_file: Path | None = None) -> bool:
        """
        Install dependencies to plugin's private deps/ directory.
        
        Args:
            requirements_file: Path to requirements.txt, None to use default
            
        Returns:
            True if installation successful
        """
        if requirements_file is None:
            requirements_file = self.plugin_dir / "requirements.txt"
        
        if not requirements_file.exists():
            logger.debug(f"No requirements.txt for {self.plugin_dir.name}")
            return True
        
        # Check if dependencies are already up to date
        if self._is_up_to_date(requirements_file):
            logger.debug(f"Dependencies already up to date for {self.plugin_dir.name}")
            return True
        
        self.deps_dir.mkdir(exist_ok=True)
        
        try:
            # Parse requirements and filter out system packages
            requirements = self._parse_requirements(requirements_file)
            to_install = [
                r for r in requirements
                if not self._is_system_package(r)
            ]
            
            if not to_install:
                logger.info(f"All dependencies satisfied by system for {self.plugin_dir.name}")
                self._save_hash(requirements_file)
                return True
            
            logger.info(f"Installing dependencies for {self.plugin_dir.name}: {to_install}")
            
            # Install to isolated deps directory
            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "pip", "install",
                    *to_install,
                    "--target", str(self.deps_dir),
                    "--upgrade",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Save hash after successful installation
            self._save_hash(requirements_file)
            
            logger.info(f"✅ Dependencies installed for {self.plugin_dir.name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install dependencies: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"❌ Error installing dependencies: {e}")
            return False
    
    def _parse_requirements(self, file: Path) -> list[str]:
        """Parse requirements.txt file."""
        requirements = []
        
        for line in file.read_text().splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Skip editable installs and options
            if line.startswith("-"):
                continue
            requirements.append(line)
        
        return requirements
    
    def _is_system_package(self, requirement: str) -> bool:
        """Check if a package is provided by the system."""
        # Extract package name (handle "package>=1.0" format)
        pkg_name = requirement.split("[")[0].split("=")[0].split("<")[0].split(">")[0].strip()
        pkg_name_lower = pkg_name.lower()
        
        return pkg_name_lower in self.SYSTEM_PACKAGES
    
    def get_path(self) -> str:
        """Get the deps directory path for sys.path."""
        return str(self.deps_dir)
    
    def list_installed(self) -> list[str]:
        """List installed packages in deps directory."""
        if not self.deps_dir.exists():
            return []
        
        packages = []
        for item in self.deps_dir.iterdir():
            if item.is_dir() and not item.name.endswith(".dist-info"):
                packages.append(item.name)
            elif item.suffix == ".py":
                packages.append(item.stem)
        
        return sorted(packages)
    
    def is_installed(self, package: str) -> bool:
        """Check if a package is installed in deps directory."""
        if not self.deps_dir.exists():
            return False
        
        # Check as directory (package)
        if (self.deps_dir / package).exists():
            return True
        
        # Check as file (module)
        if (self.deps_dir / f"{package}.py").exists():
            return True
        
        return False
