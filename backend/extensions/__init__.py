"""Unified Extension System for Octopus.

This module provides a unified way to manage skills and plugins
through a common Extension interface.
"""

from .base import Extension, PluginExtension, PluginResult, SkillExtension
from .desktop_handlers import (
    PluginGetInstalledHandler,
    PluginInstallHandler,
    PluginRemoveHandler,
    PluginRunHandler,
    SkillGetInstalledHandler,
    SkillInstallHandler,
    SkillRemoveHandler,
    SkillRunHandler,
)
from .loader import ExtensionLoader
from .plugin_dependency import DependencyManager
from .plugin_handler import PluginHandler
from .plugin_interface import PluginInterface
from .plugin_isolated_loader import IsolatedPluginImporter, PluginModuleLoader
from .plugin_skill_parser import ActionDef, PluginSkill, SkillParser
from .registry import ExtensionRegistry, get_registry

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
