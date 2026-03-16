"""Message format adapter for different LLM providers.

This module handles the conversion between internal message formats
and provider-specific formats for tool calls and responses.
"""

from enum import Enum
from typing import Any
from loguru import logger


class ProviderType(str, Enum):
    """Supported provider types."""
    OPENAI = "openai"
    OPENAI_RESPONSE = "openai-response"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure-openai"
    NEW_API = "new-api"
    CHERRYLN = "cherryln"
    OLLAMA = "ollama"


class ProviderFormat(str, Enum):
    """Message format types."""
    OPENAI = "openai"           # Standard OpenAI format
    ANTHROPIC = "anthropic"     # Anthropic format


# Mapping from provider type to message format
PROVIDER_TO_FORMAT: dict[ProviderType, ProviderFormat] = {
    ProviderType.OPENAI: ProviderFormat.OPENAI,
    ProviderType.OPENAI_RESPONSE: ProviderFormat.OPENAI,
    ProviderType.GEMINI: ProviderFormat.OPENAI,
    ProviderType.ANTHROPIC: ProviderFormat.ANTHROPIC,
    ProviderType.AZURE_OPENAI: ProviderFormat.OPENAI,
    ProviderType.NEW_API: ProviderFormat.OPENAI,
    ProviderType.CHERRYLN: ProviderFormat.OPENAI,
    ProviderType.OLLAMA: ProviderFormat.OPENAI,
}


class MessageAdapter:
    """Adapter for converting messages between different provider formats."""

    @staticmethod
    def get_format(provider_type: str) -> ProviderFormat:
        """Get the message format for a provider type.
        
        Args:
            provider_type: The provider type string.
            
        Returns:
            The corresponding ProviderFormat.
        """
        try:
            pt = ProviderType(provider_type.lower())
            return PROVIDER_TO_FORMAT.get(pt, ProviderFormat.OPENAI)
        except ValueError:
            logger.warning(f"Unknown provider type: {provider_type}, defaulting to OPENAI format")
            return ProviderFormat.OPENAI

    @staticmethod
    def adapt_messages(
        messages: list[dict[str, Any]],
        provider_type: str
    ) -> list[dict[str, Any]]:
        """Adapt messages for a specific provider.
        
        Args:
            messages: List of messages in internal format.
            provider_type: Target provider type.
            
        Returns:
            Adapted messages for the provider.
        """
        fmt = MessageAdapter.get_format(provider_type)
        
        if fmt == ProviderFormat.ANTHROPIC:
            return MessageAdapter._to_anthropic_format(messages)
        else:
            return MessageAdapter._to_openai_format(messages)

    @staticmethod
    def _to_openai_format(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert messages to strict OpenAI format.
        
        Key requirements:
        - tool role messages MUST have 'tool_call_id' field
        - assistant messages with tool_calls MUST have proper structure
        """
        adapted = []
        
        for msg in messages:
            role = msg.get("role")
            adapted_msg = dict(msg)  # Copy message
            
            if role == "tool":
                # Ensure tool_call_id is present (DeepSeek requires this)
                if "tool_call_id" not in adapted_msg:
                    # Try to get from tool_use_id (Anthropic style)
                    if "tool_use_id" in adapted_msg:
                        adapted_msg["tool_call_id"] = adapted_msg.pop("tool_use_id")
                    else:
                        logger.error(f"Tool message missing tool_call_id: {msg}")
                        # Generate a fallback ID to prevent API error
                        adapted_msg["tool_call_id"] = "unknown"
                
                # Remove Anthropic-specific fields that OpenAI doesn't accept
                adapted_msg.pop("tool_use_id", None)
                adapted_msg.pop("name", None)  # OpenAI tool messages don't have name
                
            elif role == "assistant":
                # Ensure tool_calls use OpenAI format
                if "tool_use" in adapted_msg:
                    # Convert Anthropic tool_use to OpenAI tool_calls
                    tool_calls = []
                    for tu in adapted_msg.pop("tool_use", []):
                        tool_calls.append({
                            "id": tu.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tu.get("name", ""),
                                "arguments": tu.get("input", {})
                            }
                        })
                    if tool_calls:
                        adapted_msg["tool_calls"] = tool_calls
            
            adapted.append(adapted_msg)
        
        return adapted

    @staticmethod
    def _to_anthropic_format(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert messages to Anthropic format."""
        adapted = []
        
        for msg in messages:
            role = msg.get("role")
            adapted_msg = dict(msg)
            
            if role == "tool":
                # Anthropic uses tool_use_id instead of tool_call_id
                if "tool_use_id" not in adapted_msg and "tool_call_id" in adapted_msg:
                    adapted_msg["tool_use_id"] = adapted_msg.pop("tool_call_id")
                    
            elif role == "assistant":
                # Convert OpenAI tool_calls to Anthropic tool_use
                if "tool_calls" in adapted_msg and "tool_use" not in adapted_msg:
                    tool_use = []
                    for tc in adapted_msg.pop("tool_calls", []):
                        func = tc.get("function", {})
                        args = func.get("arguments", "{}")
                        if isinstance(args, str):
                            import json
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {"raw": args}
                        
                        tool_use.append({
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args
                        })
                    if tool_use:
                        adapted_msg["tool_use"] = tool_use
            
            adapted.append(adapted_msg)
        
        return adapted

    @staticmethod
    def create_tool_result_message(
        tool_call_id: str,
        tool_name: str,
        result: str,
        provider_type: str
    ) -> dict[str, Any]:
        """Create a properly formatted tool result message.
        
        Args:
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
            provider_type: Target provider type.
            
        Returns:
            Formatted tool result message.
        """
        fmt = MessageAdapter.get_format(provider_type)
        
        if fmt == ProviderFormat.ANTHROPIC:
            return {
                "role": "tool",
                "tool_use_id": tool_call_id,
                "content": result
            }
        else:
            # OpenAI format - strictly requires tool_call_id
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result
            }

    @staticmethod
    def create_assistant_message(
        content: str | None,
        tool_calls: list[dict[str, Any]] | None,
        provider_type: str
    ) -> dict[str, Any]:
        """Create a properly formatted assistant message.
        
        Args:
            content: Message content.
            tool_calls: Optional tool calls.
            provider_type: Target provider type.
            
        Returns:
            Formatted assistant message.
        """
        fmt = MessageAdapter.get_format(provider_type)
        
        if fmt == ProviderFormat.ANTHROPIC:
            msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                tool_use = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments", "{}")
                    if isinstance(args, str):
                        import json
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"raw": args}
                    
                    tool_use.append({
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": args
                    })
                if tool_use:
                    msg["tool_use"] = tool_use
            return msg
        else:
            # OpenAI format
            msg = {"role": "assistant", "content": content or ""}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            return msg
