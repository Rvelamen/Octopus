"""Isolated module loader for plugins with dependency isolation."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger


class PluginModuleLoader:
    """
    Isolated module loader for plugins.
    
    Each plugin gets its own import namespace:
    - Dependencies are loaded from plugin's deps/ directory
    - Avoids conflicts with main environment or other plugins
    """
    
    def __init__(self, plugin_name: str, plugin_dir: Path):
        self.plugin_name = plugin_name
        self.plugin_dir = plugin_dir
        self.deps_dir = plugin_dir / "deps"
        self.handler_path = plugin_dir / "handler.py"
        
        # Track modules loaded for this plugin
        self._loaded_modules: set[str] = set()
        self._original_meta_path: list[Any] = []
    
    def setup(self) -> None:
        """Setup isolated import environment."""
        # Save original meta path
        self._original_meta_path = sys.meta_path.copy()
        
        # Insert custom finder at the beginning
        sys.meta_path.insert(0, self)
        
        # Add deps directory to sys.path for this plugin
        if self.deps_dir.exists():
            # Insert at beginning to prioritize plugin deps
            sys.path.insert(0, str(self.deps_dir))
    
    def cleanup(self) -> None:
        """Cleanup isolated import environment."""
        # Restore original meta path
        sys.meta_path = self._original_meta_path
        
        # Remove deps from sys.path
        if str(self.deps_dir) in sys.path:
            sys.path.remove(str(self.deps_dir))
        
        # Remove loaded modules
        for module_name in self._loaded_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]
    
    def find_module(self, fullname: str, path: Any = None) -> Any:
        """
        Find module - implements PEP 302 finder protocol.
        
        Prioritizes plugin's deps/ directory over system packages.
        """
        # Only handle modules that might be in plugin's deps
        if not self._should_handle(fullname):
            return None
        
        # Try to find in deps directory
        if self.deps_dir.exists():
            module_path = self._find_in_deps(fullname)
            if module_path:
                return self
        
        return None
    
    def load_module(self, fullname: str) -> ModuleType:
        """
        Load module - implements PEP 302 loader protocol.
        """
        # Check if already loaded
        if fullname in sys.modules:
            return sys.modules[fullname]
        
        # Find module path
        module_path = self._find_in_deps(fullname)
        if not module_path:
            raise ImportError(f"Cannot find module {fullname}")
        
        # Create module
        spec = importlib.util.spec_from_file_location(fullname, module_path)
        if not spec or not spec.loader:
            raise ImportError(f"Cannot create spec for {fullname}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        self._loaded_modules.add(fullname)
        
        # Execute module
        spec.loader.exec_module(module)
        
        return module
    
    def _should_handle(self, fullname: str) -> bool:
        """Check if this loader should handle the module."""
        # Don't handle standard library or system modules
        stdlib_modules = {
            'sys', 'os', 'typing', 'pathlib', 'abc', 'dataclasses',
            'json', 're', 'datetime', 'collections', 'functools',
            'itertools', 'types', 'inspect', 'importlib', 'logging',
        }
        
        base_name = fullname.split('.')[0]
        if base_name in stdlib_modules:
            return False
        
        return True
    
    def _find_in_deps(self, fullname: str) -> Path | None:
        """Find module in deps directory."""
        if not self.deps_dir.exists():
            return None
        
        parts = fullname.split('.')
        
        # Try as package (directory with __init__.py)
        pkg_path = self.deps_dir.joinpath(*parts)
        init_file = pkg_path / "__init__.py"
        if init_file.exists():
            return init_file
        
        # Try as module (single .py file)
        if len(parts) == 1:
            mod_file = self.deps_dir / f"{parts[0]}.py"
        else:
            mod_file = self.deps_dir.joinpath(*parts[:-1]) / f"{parts[-1]}.py"
        
        if mod_file.exists():
            return mod_file
        
        return None
    
    def load_handler(self) -> ModuleType:
        """Load the plugin's handler.py module."""
        if not self.handler_path.exists():
            raise FileNotFoundError(f"handler.py not found in {self.plugin_dir}")
        
        module_name = f"octopus_plugin_{self.plugin_name}"
        
        # Check if already loaded
        if module_name in sys.modules:
            return sys.modules[module_name]
        
        # Setup isolated environment
        self.setup()
        
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(
                module_name,
                self.handler_path
            )
            if not spec or not spec.loader:
                raise ImportError(f"Cannot create spec for {module_name}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            self._loaded_modules.add(module_name)
            
            # Execute
            spec.loader.exec_module(module)
            
            # Tag module with plugin info
            module.__plugin_name__ = self.plugin_name
            
            return module
            
        except Exception as e:
            # Cleanup on error
            self.cleanup()
            raise e


class IsolatedPluginImporter:
    """
    Context manager for isolated plugin imports.
    
    Usage:
        async with IsolatedPluginImporter("weather", plugin_dir) as importer:
            module = importer.load_handler()
            # Use module...
    """
    
    def __init__(self, plugin_name: str, plugin_dir: Path):
        self.loader = PluginModuleLoader(plugin_name, plugin_dir)
        self.module: ModuleType | None = None
    
    async def __aenter__(self):
        self.loader.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.loader.cleanup()
        return False
    
    def load_handler(self) -> ModuleType:
        """Load the handler module."""
        return self.loader.load_handler()
