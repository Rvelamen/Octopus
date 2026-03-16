"""Plugin environment manager with portable Python support."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


class PluginEnvironmentManager:
    """
    Manages Python environment for plugins.
    
    Priority:
    1. System Python (if available)
    2. Bundled portable Python
    3. User-installed Python
    """
    
    def __init__(self):
        self._python_exe: Optional[Path] = None
        self._pip_exe: Optional[Path] = None
        self._venv_dir: Optional[Path] = None
        
    def initialize(self) -> bool:
        """
        Initialize the plugin environment.
        
        Returns:
            True if a usable Python environment was found/created
        """
        # Try to find Python in order of preference
        self._python_exe = (
            self._find_system_python() or
            self._find_portable_python() or
            self._find_user_python()
        )
        
        if not self._python_exe:
            logger.error("No Python environment found for plugins")
            return False
        
        logger.info(f"Using Python for plugins: {self._python_exe}")
        
        # Setup plugin virtual environment
        self._setup_plugin_venv()
        
        return True
    
    def _find_system_python(self) -> Optional[Path]:
        """Find system-installed Python."""
        python_names = ["python3.11", "python3.10", "python3.9", "python3", "python"]
        
        for name in python_names:
            path = shutil.which(name)
            if path:
                exe = Path(path)
                if self._verify_python(exe):
                    logger.debug(f"Found system Python: {exe}")
                    return exe
        
        return None
    
    def _find_portable_python(self) -> Optional[Path]:
        """Find bundled portable Python."""
        # In development
        portable_paths = [
            Path(__file__).parent.parent.parent.parent / "resources" / "python-portable",
        ]
        
        # In packaged app (Electron resources)
        if getattr(sys, 'frozen', False):
            # PyInstaller bundle
            bundle_dir = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
            portable_paths.append(bundle_dir / "resources" / "python-portable")
            
            # Electron app resources
            portable_paths.append(bundle_dir.parent / "Resources" / "python-portable")
        
        # Check common locations
        system = platform.system()
        for portable_dir in portable_paths:
            if not portable_dir.exists():
                continue
            
            # Find Python executable
            if system == "Windows":
                candidates = [
                    portable_dir / "python" / "python.exe",
                    portable_dir / "python.exe",
                    portable_dir / "bin" / "python.exe",
                ]
            else:
                candidates = [
                    portable_dir / "python" / "bin" / "python3",
                    portable_dir / "python" / "bin" / "python",
                    portable_dir / "bin" / "python3",
                    portable_dir / "bin" / "python",
                ]
            
            for candidate in candidates:
                if candidate.exists() and self._verify_python(candidate):
                    logger.info(f"Found portable Python: {candidate}")
                    return candidate
        
        return None
    
    def _find_user_python(self) -> Optional[Path]:
        """Find Python in user-installed locations."""
        home = Path.home()
        system = platform.system()
        
        candidates = []
        
        if system == "Darwin":
            candidates = [
                home / ".pyenv" / "shims" / "python3",
                home / ".pyenv" / "shims" / "python",
                home / ".local" / "bin" / "python3",
                "/usr/local/bin/python3",
                "/opt/homebrew/bin/python3",
            ]
        elif system == "Linux":
            candidates = [
                home / ".pyenv" / "shims" / "python3",
                home / ".local" / "bin" / "python3",
                "/usr/bin/python3",
            ]
        elif system == "Windows":
            candidates = [
                home / "AppData" / "Local" / "Programs" / "Python" / "Python311" / "python.exe",
                home / "AppData" / "Local" / "Programs" / "Python" / "Python310" / "python.exe",
                Path("C:/Python311/python.exe"),
            ]
        
        for candidate in candidates:
            if candidate.exists() and self._verify_python(candidate):
                logger.debug(f"Found user Python: {candidate}")
                return candidate
        
        return None
    
    def _verify_python(self, python_exe: Path) -> bool:
        """Verify that the Python executable works."""
        try:
            result = subprocess.run(
                [str(python_exe), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Failed to verify Python {python_exe}: {e}")
            return False
    
    def _setup_plugin_venv(self):
        """Setup isolated virtual environment for plugins."""
        # Use user data directory for venv
        if platform.system() == "Windows":
            base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif platform.system() == "Darwin":
            base_dir = Path.home() / "Library" / "Application Support"
        else:
            base_dir = Path.home() / ".local" / "share"
        
        self._venv_dir = base_dir / "Octopus" / "plugin-env"
        
        # Create venv if it doesn't exist
        if not (self._venv_dir / "bin" / "python").exists() and not (self._venv_dir / "Scripts" / "python.exe").exists():
            logger.info(f"Creating plugin virtual environment at {self._venv_dir}")
            self._venv_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                subprocess.run(
                    [str(self._python_exe), "-m", "venv", str(self._venv_dir)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info("Plugin virtual environment created successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to create virtual environment: {e.stderr}")
                # Fall back to using base Python
                self._venv_dir = None
        
        # Update paths to use venv
        if self._venv_dir:
            if platform.system() == "Windows":
                self._python_exe = self._venv_dir / "Scripts" / "python.exe"
                self._pip_exe = self._venv_dir / "Scripts" / "pip.exe"
            else:
                self._python_exe = self._venv_dir / "bin" / "python"
                self._pip_exe = self._venv_dir / "bin" / "pip"
        else:
            # Use base Python's pip
            self._pip_exe = Path(str(self._python_exe).replace("python", "pip"))
            if not self._pip_exe.exists():
                self._pip_exe = None
    
    @property
    def python_exe(self) -> Optional[Path]:
        """Get the Python executable path."""
        return self._python_exe
    
    @property
    def pip_exe(self) -> Optional[Path]:
        """Get the pip executable path."""
        return self._pip_exe
    
    @property
    def is_available(self) -> bool:
        """Check if Python environment is available."""
        return self._python_exe is not None and self._python_exe.exists()
    
    def run_pip(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        """
        Run pip with the given arguments.
        
        Args:
            args: pip arguments
            **kwargs: additional subprocess.run arguments
            
        Returns:
            CompletedProcess instance
        """
        if not self.is_available:
            raise RuntimeError("Python environment not available")
        
        if self._pip_exe and self._pip_exe.exists():
            cmd = [str(self._pip_exe)] + args
        else:
            # Fallback to python -m pip
            cmd = [str(self._python_exe), "-m", "pip"] + args
        
        logger.debug(f"Running: {' '.join(cmd)}")
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            **kwargs
        )
    
    def install_package(self, package: str, target_dir: Optional[Path] = None) -> bool:
        """
        Install a package.
        
        Args:
            package: Package name or requirement specifier
            target_dir: Optional target directory (for isolated plugin deps)
            
        Returns:
            True if installation succeeded
        """
        try:
            args = ["install", package, "--upgrade"]
            
            if target_dir:
                args.extend(["--target", str(target_dir)])
            
            result = self.run_pip(args)
            
            if result.returncode == 0:
                logger.info(f"✅ Installed {package}")
                return True
            else:
                logger.error(f"❌ Failed to install {package}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error installing {package}: {e}")
            return False
    
    def get_version(self) -> Optional[str]:
        """Get Python version string."""
        if not self.is_available:
            return None
        
        try:
            result = subprocess.run(
                [str(self._python_exe), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return (result.stdout or result.stderr).strip()
        except Exception:
            return None


# Global instance
_plugin_env_manager: Optional[PluginEnvironmentManager] = None


def get_plugin_env_manager() -> PluginEnvironmentManager:
    """Get the global plugin environment manager instance."""
    global _plugin_env_manager
    if _plugin_env_manager is None:
        _plugin_env_manager = PluginEnvironmentManager()
        _plugin_env_manager.initialize()
    return _plugin_env_manager
