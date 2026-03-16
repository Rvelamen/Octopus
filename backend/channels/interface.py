"""Channel interface for extended capabilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChannelResult:
    """Result of a channel action execution."""
    success: bool
    data: Any = None
    error: str = None


class ChannelInterface(ABC):
    """
    Extended interface for channels that support additional actions.
    
    This interface allows channels to expose their capabilities through
    a unified API, avoiding tool explosion.
    """
    
    name: str = "base"
    
    @property
    def actions(self) -> list[str]:
        """
        Return list of supported action names.
        
        These actions can be invoked via the channel tool.
        Example: ["send_message", "send_file", "read_doc"]
        """
        return []
    
    async def execute(
        self,
        action: str,
        **kwargs: Any
    ) -> ChannelResult:
        """
        Execute an action on this channel.
        
        Args:
            action: The action name to execute
            **kwargs: Action-specific parameters
            
        Returns:
            ChannelResult with success status and data/error
        """
        method_name = f"action_{action}"
        method = getattr(self, method_name, None)
        
        if not method:
            return ChannelResult(
                success=False,
                error=f"Action '{action}' not supported by {self.name} channel. "
                      f"Supported: {', '.join(self.actions)}"
            )
        
        try:
            result = await method(**kwargs)
            if isinstance(result, ChannelResult):
                return result
            return ChannelResult(success=True, data=result)
        except Exception as e:
            return ChannelResult(success=False, error=str(e))
    
    async def action_send_message(
        self,
        chat_id: str,
        content: str,
        **kwargs: Any
    ) -> ChannelResult:
        """Send a text message. Override if supported."""
        return ChannelResult(
            success=False,
            error=f"send_message not implemented for {self.name}"
        )
    
    async def action_send_file(
        self,
        chat_id: str,
        file_path: str,
        **kwargs: Any
    ) -> ChannelResult:
        """Send a file. Override if supported."""
        return ChannelResult(
            success=False,
            error=f"send_file not implemented for {self.name}"
        )
    
    async def action_send_image(
        self,
        chat_id: str,
        image_path: str,
        **kwargs: Any
    ) -> ChannelResult:
        """Send an image. Override if supported."""
        return ChannelResult(
            success=False,
            error=f"send_image not implemented for {self.name}"
        )
