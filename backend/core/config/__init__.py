"""Configuration module for backend."""

from backend.core.config.loader import get_config_path, load_config
from backend.core.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
