"""Session management commands for multi-session support."""

import re
from dataclasses import dataclass
from typing import Callable, Awaitable

from loguru import logger

from backend.data.session_manager import SessionManager


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    message: str
    data: dict | None = None


class SessionCommandHandler:
    """Handler for session management commands."""
    
    # Command patterns
    CMD_NEW = r'^/new\s*(?:session)?\s*(\w+)?$'
    CMD_SWITCH = r'^/switch\s+(?:session\s+)?(\d+)$'
    CMD_DELETE = r'^/delete\s+(?:session\s+)?(\d+)$'
    CMD_LIST = r'^/list\s*(?:sessions?)?$'
    CMD_HELP = r'^/help\s*(?:session)?$'
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
    
    async def handle(self, content: str | list, session_key: str) -> CommandResult | None:
        """
        Handle a potential command message.

        Args:
            content: Message content to check for commands (string or multi-modal list).
            session_key: Current session key (channel:chat_id).

        Returns:
            CommandResult if a command was handled, None otherwise.
        """
        # Handle multi-modal content - extract text for command checking
        if isinstance(content, list):
            # Multi-modal message, check if any text item starts with /
            # Handle both dict and MessageContentItem objects
            text_items = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_items.append(item.get("text", ""))
                else:
                    # MessageContentItem object
                    if hasattr(item, 'type') and item.type == "text":
                        text_items.append(getattr(item, 'text', ""))
            if not text_items:
                return None
            content = text_items[0]

        content = content.strip()
        
        # Check for /new command
        match = re.match(self.CMD_NEW, content, re.IGNORECASE)
        if match:
            instance_name = match.group(1)
            return await self._handle_new(session_key, instance_name)
        
        # Check for /switch command
        match = re.match(self.CMD_SWITCH, content, re.IGNORECASE)
        if match:
            instance_id = int(match.group(1))
            return await self._handle_switch(session_key, instance_id)
        
        # Check for /delete command
        match = re.match(self.CMD_DELETE, content, re.IGNORECASE)
        if match:
            instance_id = int(match.group(1))
            return await self._handle_delete(session_key, instance_id)
        
        # Check for /list command
        match = re.match(self.CMD_LIST, content, re.IGNORECASE)
        if match:
            return await self._handle_list(session_key)
        
        # Check for /help command
        match = re.match(self.CMD_HELP, content, re.IGNORECASE)
        if match:
            return await self._handle_help()
        
        return None
    
    async def _handle_new(self, session_key: str, instance_name: str | None) -> CommandResult:
        """Handle /new command to create a new session instance."""
        try:
            # Generate default name if not provided
            if not instance_name:
                # Get existing instances to generate unique name
                success, instances, _ = self.session_manager.list_instances(session_key)
                if success:
                    existing_names = {inst["name"] for inst in instances}
                    counter = 1
                    while f"session_{counter}" in existing_names:
                        counter += 1
                    instance_name = f"session_{counter}"
                else:
                    instance_name = "session_1"
            
            # Validate instance name
            if not self._validate_instance_name(instance_name):
                return CommandResult(
                    success=False,
                    message=f"Invalid session name: '{instance_name}'. Use only letters, numbers, underscores, and hyphens."
                )
            
            # Create new instance
            success, message = self.session_manager.create_instance(session_key, instance_name)
            
            if success:
                return CommandResult(
                    success=True,
                    message=f"✅ {message}\n\nYou can now start a fresh conversation. Previous messages are preserved in the old session.",
                    data={"action": "create", "instance_name": instance_name}
                )
            else:
                return CommandResult(
                    success=False,
                    message=f"❌ Failed to create session: {message}"
                )
                
        except Exception as e:
            logger.error(f"Error creating new session: {e}")
            return CommandResult(
                success=False,
                message=f"❌ An error occurred while creating the session: {str(e)}"
            )
    
    async def _handle_switch(self, session_key: str, instance_id: int) -> CommandResult:
        """Handle /switch command to switch to a different session instance."""
        try:
            success, message = self.session_manager.switch_instance(session_key, instance_id)
            
            if success:
                return CommandResult(
                    success=True,
                    message=f"✅ {message}\n\nYou are now chatting in this session.",
                    data={"action": "switch", "instance_id": instance_id}
                )
            else:
                return CommandResult(
                    success=False,
                    message=f"❌ Failed to switch session: {message}"
                )
                
        except Exception as e:
            logger.error(f"Error switching session: {e}")
            return CommandResult(
                success=False,
                message=f"❌ An error occurred while switching sessions: {str(e)}"
            )
    
    async def _handle_delete(self, session_key: str, instance_id: int) -> CommandResult:
        """Handle /delete command to delete a session instance."""
        try:
            # Get instance info before deletion for the message
            success, instances, _ = self.session_manager.list_instances(session_key)
            target_instance = None
            if success:
                target_instance = next((inst for inst in instances if inst["id"] == instance_id), None)
            
            if not target_instance:
                return CommandResult(
                    success=False,
                    message=f"❌ Session instance {instance_id} not found"
                )
            
            instance_name = target_instance["name"]
            is_active = target_instance["is_active"]
            
            # Confirm deletion if it's the active session
            warning = ""
            if is_active:
                warning = "\n\n⚠️ This is your current active session. You will be switched to another session after deletion."
            
            # Delete the instance
            success, message = self.session_manager.delete_instance_by_id(session_key, instance_id)
            
            if success:
                return CommandResult(
                    success=True,
                    message=f"✅ {message}{warning}\n\nUse `/list` to see your remaining sessions.",
                    data={"action": "delete", "instance_id": instance_id, "instance_name": instance_name}
                )
            else:
                return CommandResult(
                    success=False,
                    message=f"❌ Failed to delete session: {message}"
                )
                
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return CommandResult(
                success=False,
                message=f"❌ An error occurred while deleting the session: {str(e)}"
            )
    
    async def _handle_list(self, session_key: str) -> CommandResult:
        """Handle /list command to list all session instances."""
        try:
            success, instances, message = self.session_manager.list_instances(session_key)
            
            if not success:
                return CommandResult(
                    success=False,
                    message=f"❌ Failed to list sessions: {message}"
                )
            
            if not instances:
                return CommandResult(
                    success=True,
                    message="📋 No sessions found. Use `/new` to create a new session.",
                    data={"instances": []}
                )
            
            # Format the list
            lines = ["📋 Your Sessions:", ""]
            
            for inst in instances:
                active_marker = "▶️" if inst["is_active"] else "  "
                name = inst["name"]
                msg_count = inst["message_count"]
                created = inst["created_at"][:10]  # Just the date part
                
                lines.append(f"{active_marker} ID: {inst['id']} | {name}")
                lines.append(f"     Messages: {msg_count} | Created: {created}")
                lines.append("")
            
            lines.append("Use `/switch <ID>` to switch to a session.")
            lines.append("Use `/new [name]` to create a new session.")
            
            return CommandResult(
                success=True,
                message="\n".join(lines),
                data={"instances": instances}
            )
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return CommandResult(
                success=False,
                message=f"❌ An error occurred while listing sessions: {str(e)}"
            )
    
    async def _handle_help(self) -> CommandResult:
        """Handle /help command to show session management help."""
        help_text = """📝 Session Management Commands

Available commands:

/new [name]      - Create a new session instance
                   Example: /new project_a
                   If name is omitted, auto-generates one

/switch <ID>     - Switch to a session by ID
                   Example: /switch 5

/delete <ID>     - Delete a session by ID
                   Example: /delete 3
                   Cannot delete the last remaining session

/list            - List all your sessions with details

/help            - Show this help message

What are sessions?
------------------
Sessions allow you to have multiple independent conversations 
with the same contact. Each session has its own message history.

• Use /new to start a fresh conversation
• Use /switch to return to a previous conversation  
• Use /delete to remove a session you no longer need
• Use /list to see all your conversations
"""
        
        return CommandResult(
            success=True,
            message=help_text,
            data={"action": "help"}
        )
    
    def _validate_instance_name(self, name: str) -> bool:
        """Validate instance name format."""
        if not name:
            return False
        if len(name) > 50:
            return False
        # Allow letters, numbers, underscores, hyphens
        return bool(re.match(r'^[\w\-]+$', name))
    
    def is_command(self, content: str) -> bool:
        """Check if content is a session command."""
        content = content.strip()
        patterns = [self.CMD_NEW, self.CMD_SWITCH, self.CMD_DELETE, self.CMD_LIST, self.CMD_HELP]
        for pattern in patterns:
            if re.match(pattern, content, re.IGNORECASE):
                return True
        return False


# Convenience function for integration
async def handle_session_command(
    content: str, 
    session_key: str, 
    session_manager: SessionManager
) -> CommandResult | None:
    """
    Convenience function to handle session commands.
    
    Args:
        content: Message content.
        session_key: Current session key.
        session_manager: Session manager instance.
        
    Returns:
        CommandResult if handled as command, None otherwise.
    """
    handler = SessionCommandHandler(session_manager)
    return await handler.handle(content, session_key)
