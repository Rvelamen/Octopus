"""Configuration module for backend."""

from backend.core.config.loader import load_config, get_config_path
from backend.core.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
