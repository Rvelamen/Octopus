"""Desktop channel configuration."""

from typing import Any


class DesktopConfig:
    """Configuration for DesktopChannel."""

    def __init__(self):
        self.allow_from: list[str] = []


def get_desktop_config(**kwargs: Any) -> DesktopConfig:
    """Create DesktopConfig with custom settings."""
    config = DesktopConfig()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config
