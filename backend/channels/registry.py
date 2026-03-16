"""Channel registry for managing channel capabilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.channels.interface import ChannelInterface


class ChannelRegistry:
    """
    Registry for channel instances and their capabilities.
    
    This registry allows tools to discover and invoke channel actions
    without knowing the specific channel implementations.
    """
    
    _channels: dict[str, "ChannelInterface"] = {}
    
    @classmethod
    def register(cls, channel: "ChannelInterface") -> None:
        """Register a channel instance."""
        cls._channels[channel.name] = channel
    
    @classmethod
    def get(cls, name: str) -> "ChannelInterface | None":
        """Get a channel by name."""
        return cls._channels.get(name)
    
    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered channel names."""
        return list(cls._channels.keys())
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered channels (mainly for testing)."""
        cls._channels.clear()


def get_channel_registry() -> type[ChannelRegistry]:
    """Get the channel registry class."""
    return ChannelRegistry
