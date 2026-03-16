"""Chat channels module with plugin architecture."""

from backend.channels.base import BaseChannel
from backend.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
