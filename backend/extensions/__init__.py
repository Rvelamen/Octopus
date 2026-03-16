"""Unified Extension System for Tracebot.

This module provides a unified way to manage skills and plugins
through a common Extension interface.
"""

from .base import Extension, SkillExtension, PluginExtension, PluginResult
from .loader import ExtensionLoader
from .registry import ExtensionRegistry, get_registry
from .plugin_interface import PluginInterface
from .plugin_handler import PluginHandler
from .plugin_skill_parser import PluginSkill, SkillParser, ActionDef
from .plugin_dependency import DependencyManager
from .plugin_isolated_loader import PluginModuleLoader, IsolatedPluginImporter
from .desktop_handlers import (
    SkillInstallHandler,
    SkillGetInstalledHandler,
    SkillRemoveHandler,
    SkillRunHandler,
    PluginInstallHandler,
    PluginGetInstalledHandler,
    PluginRemoveHandler,
    PluginRunHandler,
)

__all__ = [
    # Base classes
    "Extension",
    "SkillExtension",
    "PluginExtension",
    "PluginResult",
    # Loader and registry
    "ExtensionLoader",
    "ExtensionRegistry",
    "get_registry",
    # Plugin classes
    "PluginInterface",
    "PluginHandler",
    "PluginSkill",
    "SkillParser",
    "ActionDef",
    "DependencyManager",
    "PluginModuleLoader",
    "IsolatedPluginImporter",
    # Desktop handlers
    "SkillInstallHandler",
    "SkillGetInstalledHandler",
    "SkillRemoveHandler",
    "SkillRunHandler",
    "PluginInstallHandler",
    "PluginGetInstalledHandler",
    "PluginRemoveHandler",
    "PluginRunHandler",
]
