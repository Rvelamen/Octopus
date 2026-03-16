"""WebSocket message protocol definitions for Desktop channel."""

from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field


class MessageType(Enum):
    """Message types for WebSocket communication."""

    # Client -> Server
    CHAT = "chat"                    # Send a chat message
    GET_CONFIG = "get_config"        # Get current configuration
    SAVE_CONFIG = "save_config"      # Save configuration
    PING = "ping"                    # Keep-alive ping
    GET_MODELS = "get_models"        # Get available models for a provider

    # MCP - Client -> Server
    MCP_GET_STATUS = "mcp_get_status"              # Get MCP system status
    MCP_GET_SERVERS = "mcp_get_servers"            # Get all MCP servers
    MCP_GET_SERVER_TOOLS = "mcp_get_server_tools"  # Get tools for a server
    MCP_ADD_SERVER = "mcp_add_server"              # Add new MCP server
    MCP_DELETE_SERVER = "mcp_delete_server"        # Delete MCP server
    MCP_UPDATE_SERVER = "mcp_update_server"        # Update server config
    MCP_UPDATE_TOOL = "mcp_update_tool"            # Update tool config
    MCP_DISCOVER_TOOLS = "mcp_discover_tools"      # Discover tools from server
    MCP_CONNECT_SERVER = "mcp_connect_server"      # Connect to a server
    MCP_DISCONNECT_SERVER = "mcp_disconnect_server"  # Disconnect from server
    MCP_CALL_TOOL = "mcp_call_tool"                # Call a tool
    MCP_GET_CONFIG = "mcp_get_config"              # Get MCP configuration
    MCP_UPDATE_CONFIG = "mcp_update_config"        # Update MCP configuration

    # Extensions - Client -> Server (Unified)
    EXTENSION_GET_LIST = "extension_get_list"      # Get extensions list (market or installed)
    EXTENSION_INSTALL = "extension_install"        # Install an extension
    EXTENSION_UNINSTALL = "extension_uninstall"    # Uninstall an extension
    EXTENSION_RUN = "extension_run"                # Run an extension
    EXTENSION_CONFIG = "extension_config"          # Configure extension (save env vars)

    # Session History - Client -> Server
    SESSION_GET_CHANNELS = "session_get_channels"              # Get all channels
    SESSION_GET_CHANNEL_SESSIONS = "session_get_channel_sessions"  # Get sessions for a channel
    SESSION_GET_SESSION_DETAIL = "session_get_session_detail"      # Get session detail with instances
    SESSION_GET_MESSAGES = "session_get_messages"                  # Get messages for an instance
    SESSION_DELETE_INSTANCE = "session_delete_instance"            # Delete a session instance
    SESSION_CREATE = "session_create"                              # Create a new session with instance
    SESSION_SET_ACTIVE = "session_set_active"                      # Set an instance as active

    # Workspace File System - Client -> Server
    WORKSPACE_LIST = "workspace_list"                    # List directory contents
    WORKSPACE_READ = "workspace_read"                    # Read file content
    WORKSPACE_WRITE = "workspace_write"                  # Write file content
    WORKSPACE_DELETE = "workspace_delete"                # Delete file or directory
    WORKSPACE_MKDIR = "workspace_mkdir"                  # Create directory
    WORKSPACE_RENAME = "workspace_rename"                # Rename file or directory
    WORKSPACE_GET_ROOT = "workspace_get_root"            # Get workspace root path

    # Cron - Client -> Server
    CRON_GET_JOBS = "cron_get_jobs"                      # Get all cron jobs
    CRON_ADD_JOB = "cron_add_job"                        # Add a new cron job
    CRON_DELETE_JOB = "cron_delete_job"                  # Delete a cron job
    CRON_TOGGLE_JOB = "cron_toggle_job"                  # Enable/disable a cron job
    CRON_RUN_JOB = "cron_run_job"                        # Run a cron job manually

    # Agent - Client -> Server
    AGENT_GET_LIST = "agent_get_list"                    # Get all agents
    AGENT_GET_SOUL = "agent_get_soul"                    # Get agent SOUL.md content
    AGENT_SAVE_SOUL = "agent_save_soul"                  # Save agent SOUL.md content
    AGENT_DELETE = "agent_delete"                        # Delete an agent
    AGENT_GET_SYSTEM_FILES = "agent_get_system_files"    # Get system agent file list
    AGENT_GET_SYSTEM_FILE = "agent_get_system_file"      # Get system agent file content
    AGENT_SAVE_SYSTEM_FILE = "agent_save_system_file"    # Save system agent file content

    # System - Client -> Server
    RESTART_SERVICE = "restart_service"                  # Restart backend service

    # Image - Client -> Server
    IMAGE_UPLOAD = "image_upload"                              # Upload image
    IMAGE_ANALYZE = "image_analyze"                            # Analyze image request
    IMAGE_GENERATE = "image_generate"                          # Generate image request
    IMAGE_GET_UNDERSTANDING_PROVIDERS = "image_get_understanding_providers"  # Get understanding providers
    IMAGE_GET_GENERATION_PROVIDERS = "image_get_generation_providers"        # Get generation providers
    IMAGE_ADD_UNDERSTANDING_PROVIDER = "image_add_understanding_provider"    # Add understanding provider
    IMAGE_UPDATE_UNDERSTANDING_PROVIDER = "image_update_understanding_provider"  # Update understanding provider
    IMAGE_DELETE_UNDERSTANDING_PROVIDER = "image_delete_understanding_provider"  # Delete understanding provider
    IMAGE_ADD_GENERATION_PROVIDER = "image_add_generation_provider"          # Add generation provider
    IMAGE_UPDATE_GENERATION_PROVIDER = "image_update_generation_provider"    # Update generation provider
    IMAGE_DELETE_GENERATION_PROVIDER = "image_delete_generation_provider"    # Delete generation provider

    # Server -> Client
    ACK = "ack"                      # Message acknowledged
    CHAT_RESPONSE = "chat_response"  # Chat response (full)
    AGENT_START = "agent_start"      # Agent started processing
    AGENT_CHUNK = "agent_chunk"      # Streaming chunk
    AGENT_FINISH = "agent_finish"    # Agent finished
    CONFIG = "config"                # Configuration data
    ERROR = "error"                  # Error message
    PONG = "pong"                    # Keep-alive pong
    MODELS = "models"                # Available models list

    # MCP - Server -> Client
    MCP_STATUS = "mcp_status"              # MCP status response
    MCP_SERVERS = "mcp_servers"            # MCP servers list
    MCP_SERVER_TOOLS = "mcp_server_tools"  # MCP server tools
    MCP_SERVER_ADDED = "mcp_server_added"      # Server added confirmation
    MCP_SERVER_DELETED = "mcp_server_deleted"  # Server deleted confirmation
    MCP_SERVER_UPDATED = "mcp_server_updated"  # Server updated confirmation
    MCP_TOOL_UPDATED = "mcp_tool_updated"      # Tool updated confirmation
    MCP_TOOLS_DISCOVERED = "mcp_tools_discovered"  # Tools discovered
    MCP_SERVER_CONNECTED = "mcp_server_connected"    # Server connected
    MCP_SERVER_DISCONNECTED = "mcp_server_disconnected"  # Server disconnected
    MCP_TOOL_RESULT = "mcp_tool_result"    # Tool call result
    MCP_CONFIG = "mcp_config"              # MCP configuration
    MCP_CONFIG_UPDATED = "mcp_config_updated"  # Config updated confirmation
    MCP_STATE_CHANGE = "mcp_state_change"  # MCP state change event

    # Extensions - Server -> Client (Unified)
    EXTENSION_LIST = "extension_list"              # List of extensions
    EXTENSION_INSTALLING = "extension_installing"  # Extension installation started
    EXTENSION_INSTALLED = "extension_installed"    # Extension installation completed
    EXTENSION_INSTALL_ERROR = "extension_install_error"  # Extension installation failed
    EXTENSION_UNINSTALLED = "extension_uninstalled"      # Extension uninstalled
    EXTENSION_RUNNING = "extension_running"        # Extension is running
    EXTENSION_RUN_RESULT = "extension_run_result"  # Extension run result
    EXTENSION_CONFIG_REQUIRED = "extension_config_required"  # Extension requires configuration
    EXTENSION_CONFIG_SAVED = "extension_config_saved"        # Extension config saved

    # Session History - Server -> Client
    SESSION_CHANNELS = "session_channels"              # List of channels
    SESSION_CHANNEL_SESSIONS = "session_channel_sessions"  # Sessions for a channel
    SESSION_DETAIL = "session_detail"                  # Session detail with instances
    SESSION_MESSAGES = "session_messages"              # Messages for an instance
    SESSION_INSTANCE_DELETED = "session_instance_deleted"  # Instance deleted confirmation
    SESSION_CREATED = "session_created"                # Session created confirmation
    SESSION_ACTIVE_SET = "session_active_set"          # Active instance set confirmation

    # Workspace File System - Server -> Client
    WORKSPACE_LIST_RESULT = "workspace_list_result"    # Directory listing result
    WORKSPACE_READ_RESULT = "workspace_read_result"    # File content result
    WORKSPACE_WRITE_RESULT = "workspace_write_result"  # Write success confirmation
    WORKSPACE_DELETE_RESULT = "workspace_delete_result"  # Delete success confirmation
    WORKSPACE_MKDIR_RESULT = "workspace_mkdir_result"  # Mkdir success confirmation
    WORKSPACE_RENAME_RESULT = "workspace_rename_result"  # Rename success confirmation
    WORKSPACE_ROOT = "workspace_root"                  # Workspace root path

    # Cron - Server -> Client
    CRON_JOBS = "cron_jobs"                            # List of cron jobs
    CRON_JOB_ADDED = "cron_job_added"                  # Job added confirmation
    CRON_JOB_DELETED = "cron_job_deleted"              # Job deleted confirmation
    CRON_JOB_TOGGLED = "cron_job_toggled"              # Job toggled confirmation
    CRON_JOB_RUN = "cron_job_run"                      # Job run confirmation

    # Agent - Server -> Client
    AGENT_LIST = "agent_list"                          # List of agents
    AGENT_SOUL = "agent_soul"                          # Agent SOUL.md content
    AGENT_SAVED = "agent_saved"                        # Agent saved confirmation
    AGENT_DELETED = "agent_deleted"                    # Agent deleted confirmation
    AGENT_SYSTEM_FILES = "agent_system_files"          # System agent file list
    AGENT_SYSTEM_FILE = "agent_system_file"            # System agent file content
    AGENT_SYSTEM_FILE_SAVED = "agent_system_file_saved"  # System agent file saved

    # System - Server -> Client
    SERVICE_RESTARTING = "service_restarting"          # Service is restarting

    # Image - Server -> Client
    IMAGE_UPLOADED = "image_uploaded"                        # Image upload confirmation
    IMAGE_ANALYSIS_RESULT = "image_analysis_result"          # Image analysis result
    IMAGE_GENERATED = "image_generated"                      # Image generated confirmation
    IMAGE_GENERATION_PROGRESS = "image_generation_progress"  # Generation progress
    IMAGE_UNDERSTANDING_PROVIDERS = "image_understanding_providers"  # Understanding providers list
    IMAGE_GENERATION_PROVIDERS = "image_generation_providers"        # Generation providers list
    IMAGE_PROVIDER_ADDED = "image_provider_added"            # Provider added confirmation
    IMAGE_PROVIDER_UPDATED = "image_provider_updated"        # Provider updated confirmation
    IMAGE_PROVIDER_DELETED = "image_provider_deleted"        # Provider deleted confirmation

    # Provider - Client -> Server
    PROVIDER_GET_ALL = "provider_get_all"                    # Get all providers
    PROVIDER_GET = "provider_get"                            # Get provider by ID
    PROVIDER_ADD = "provider_add"                           # Add new provider
    PROVIDER_UPDATE = "provider_update"                     # Update provider
    PROVIDER_DELETE = "provider_delete"                     # Delete provider
    PROVIDER_ENABLE = "provider_enable"                     # Enable/disable provider

    # Model - Client -> Server
    MODEL_GET_ALL = "model_get_all"                         # Get all models for a provider
    MODEL_GET = "model_get"                                 # Get model by ID
    MODEL_ADD = "model_add"                                 # Add new model
    MODEL_UPDATE = "model_update"                           # Update model
    MODEL_DELETE = "model_delete"                           # Delete model
    MODEL_SET_DEFAULT = "model_set_default"                 # Set default model

    # Settings - Client -> Server
    SETTINGS_GET = "settings_get"                           # Get settings
    SETTINGS_SET = "settings_set"                           # Set settings

    # Provider - Server -> Client
    PROVIDERS = "providers"                                 # All providers list
    PROVIDER = "provider"                                   # Single provider
    PROVIDER_ADDED = "provider_added"                      # Provider added confirmation
    PROVIDER_UPDATED = "provider_updated"                   # Provider updated confirmation
    PROVIDER_DELETED = "provider_deleted"                   # Provider deleted confirmation

    # Model - Server -> Client
    MODELS_LIST = "models_list"                             # Models list for a provider
    MODEL_ITEM = "model_item"                              # Single model
    MODEL_ADDED = "model_added"                             # Model added confirmation
    MODEL_UPDATED = "model_updated"                         # Model updated confirmation
    MODEL_DELETED = "model_deleted"                         # Model deleted confirmation

    # Settings - Server -> Client
    SETTINGS = "settings"                                   # Settings data

    # Agent Defaults - Client -> Server
    AGENT_DEFAULTS_GET = "agent_defaults_get"               # Get agent defaults
    AGENT_DEFAULTS_UPDATE = "agent_defaults_update"         # Update agent defaults
    GET_ENABLED_MODELS = "get_enabled_models"               # Get all enabled models from enabled providers

    # Agent Defaults - Server -> Client
    AGENT_DEFAULTS = "agent_defaults"                       # Agent defaults data
    AGENT_DEFAULTS_UPDATED = "agent_defaults_updated"       # Agent defaults updated confirmation
    ENABLED_MODELS = "enabled_models"                       # All enabled models from enabled providers

    # Channel - Client -> Server
    CHANNEL_GET_LIST = "channel_get_list"                   # Get all channel configs
    CHANNEL_UPDATE = "channel_update"                       # Update channel config
    CHANNEL_DELETE = "channel_delete"                       # Delete channel config

    # Channel - Server -> Client
    CHANNEL_LIST = "channel_list"                           # All channel configs
    CHANNEL_UPDATED = "channel_updated"                     # Channel config updated confirmation
    CHANNEL_DELETED = "channel_deleted"                     # Channel config deleted confirmation

    # Tool - Client -> Server
    TOOL_GET_CONFIG = "tool_get_config"                     # Get tool configs
    TOOL_UPDATE_CONFIG = "tool_update_config"               # Update tool config

    # Tool - Server -> Client
    TOOL_CONFIG = "tool_config"                             # Tool configs
    TOOL_UPDATED = "tool_updated"                           # Tool config updated confirmation

    # Image Provider - Client -> Server
    IMAGE_GET_PROVIDERS = "image_get_providers"             # Get image providers
    IMAGE_SET_DEFAULT_PROVIDER = "image_set_default_provider"  # Set default image provider

    # Image Provider - Server -> Client
    IMAGE_PROVIDERS = "image_providers"                     # Image providers list
    IMAGE_DEFAULT_PROVIDER_UPDATED = "image_default_provider_updated"  # Default provider updated


@dataclass
class WSMessage:
    """WebSocket message structure."""
    type: MessageType
    request_id: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "request_id": self.request_id,
            "data": self.data
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WSMessage":
        """Create message from dictionary."""
        msg_type = data.get("type", "")
        # Handle both enum and string types
        if isinstance(msg_type, str):
            try:
                msg_type = MessageType(msg_type)
            except ValueError:
                msg_type = msg_type  # Keep as string if not in enum
        
        return cls(
            type=msg_type,
            request_id=data.get("request_id"),
            data=data.get("data", {})
        )


# Message type validation
CLIENT_MESSAGE_TYPES = {
    MessageType.CHAT,
    MessageType.GET_CONFIG,
    MessageType.SAVE_CONFIG,
    MessageType.PING,
    MessageType.GET_MODELS,
    MessageType.MCP_GET_STATUS,
    MessageType.MCP_GET_SERVERS,
    MessageType.MCP_GET_SERVER_TOOLS,
    MessageType.MCP_ADD_SERVER,
    MessageType.MCP_DELETE_SERVER,
    MessageType.MCP_UPDATE_SERVER,
    MessageType.MCP_UPDATE_TOOL,
    MessageType.MCP_DISCOVER_TOOLS,
    MessageType.MCP_CONNECT_SERVER,
    MessageType.MCP_DISCONNECT_SERVER,
    MessageType.MCP_CALL_TOOL,
    MessageType.MCP_GET_CONFIG,
    MessageType.MCP_UPDATE_CONFIG,
    MessageType.EXTENSION_GET_LIST,
    MessageType.EXTENSION_INSTALL,
    MessageType.EXTENSION_UNINSTALL,
    MessageType.EXTENSION_RUN,
    MessageType.EXTENSION_CONFIG,
    MessageType.SESSION_GET_CHANNELS,
    MessageType.SESSION_GET_CHANNEL_SESSIONS,
    MessageType.SESSION_GET_SESSION_DETAIL,
    MessageType.SESSION_GET_MESSAGES,
    MessageType.SESSION_DELETE_INSTANCE,
    MessageType.SESSION_CREATE,
    MessageType.SESSION_SET_ACTIVE,
    MessageType.WORKSPACE_LIST,
    MessageType.WORKSPACE_READ,
    MessageType.WORKSPACE_WRITE,
    MessageType.WORKSPACE_DELETE,
    MessageType.WORKSPACE_MKDIR,
    MessageType.WORKSPACE_RENAME,
    MessageType.WORKSPACE_GET_ROOT,
    MessageType.CRON_GET_JOBS,
    MessageType.CRON_ADD_JOB,
    MessageType.CRON_DELETE_JOB,
    MessageType.CRON_TOGGLE_JOB,
    MessageType.CRON_RUN_JOB,
    MessageType.AGENT_GET_LIST,
    MessageType.AGENT_GET_SOUL,
    MessageType.AGENT_SAVE_SOUL,
    MessageType.AGENT_DELETE,
    MessageType.AGENT_GET_SYSTEM_FILES,
    MessageType.AGENT_GET_SYSTEM_FILE,
    MessageType.AGENT_SAVE_SYSTEM_FILE,
    MessageType.RESTART_SERVICE,
    MessageType.IMAGE_UPLOAD,
    MessageType.IMAGE_ANALYZE,
    MessageType.IMAGE_GENERATE,
    MessageType.IMAGE_GET_UNDERSTANDING_PROVIDERS,
    MessageType.IMAGE_GET_GENERATION_PROVIDERS,
    MessageType.IMAGE_ADD_UNDERSTANDING_PROVIDER,
    MessageType.IMAGE_UPDATE_UNDERSTANDING_PROVIDER,
    MessageType.IMAGE_DELETE_UNDERSTANDING_PROVIDER,
    MessageType.IMAGE_ADD_GENERATION_PROVIDER,
    MessageType.IMAGE_UPDATE_GENERATION_PROVIDER,
    MessageType.IMAGE_DELETE_GENERATION_PROVIDER,
    # Provider
    MessageType.PROVIDER_GET_ALL,
    MessageType.PROVIDER_GET,
    MessageType.PROVIDER_ADD,
    MessageType.PROVIDER_UPDATE,
    MessageType.PROVIDER_DELETE,
    MessageType.PROVIDER_ENABLE,
    # Model
    MessageType.MODEL_GET_ALL,
    MessageType.MODEL_GET,
    MessageType.MODEL_ADD,
    MessageType.MODEL_UPDATE,
    MessageType.MODEL_DELETE,
    MessageType.MODEL_SET_DEFAULT,
    # Settings
    MessageType.SETTINGS_GET,
    MessageType.SETTINGS_SET,
    # Agent Defaults
    MessageType.AGENT_DEFAULTS_GET,
    MessageType.AGENT_DEFAULTS_UPDATE,
    MessageType.GET_ENABLED_MODELS,
    # Channel
    MessageType.CHANNEL_GET_LIST,
    MessageType.CHANNEL_UPDATE,
    MessageType.CHANNEL_DELETE,
    # Tool
    MessageType.TOOL_GET_CONFIG,
    MessageType.TOOL_UPDATE_CONFIG,
    # Image Provider
    MessageType.IMAGE_GET_PROVIDERS,
    MessageType.IMAGE_SET_DEFAULT_PROVIDER,
}

SERVER_MESSAGE_TYPES = {
    MessageType.ACK,
    MessageType.CHAT_RESPONSE,
    MessageType.AGENT_START,
    MessageType.AGENT_CHUNK,
    MessageType.AGENT_FINISH,
    MessageType.CONFIG,
    MessageType.ERROR,
    MessageType.PONG,
    MessageType.MODELS,
    MessageType.MCP_STATUS,
    MessageType.MCP_SERVERS,
    MessageType.MCP_SERVER_TOOLS,
    MessageType.MCP_SERVER_ADDED,
    MessageType.MCP_SERVER_DELETED,
    MessageType.MCP_SERVER_UPDATED,
    MessageType.MCP_TOOL_UPDATED,
    MessageType.MCP_TOOLS_DISCOVERED,
    MessageType.MCP_SERVER_CONNECTED,
    MessageType.MCP_SERVER_DISCONNECTED,
    MessageType.MCP_TOOL_RESULT,
    MessageType.MCP_CONFIG,
    MessageType.MCP_CONFIG_UPDATED,
    MessageType.MCP_STATE_CHANGE,
    MessageType.EXTENSION_LIST,
    MessageType.EXTENSION_INSTALLING,
    MessageType.EXTENSION_INSTALLED,
    MessageType.EXTENSION_INSTALL_ERROR,
    MessageType.EXTENSION_UNINSTALLED,
    MessageType.EXTENSION_RUNNING,
    MessageType.EXTENSION_RUN_RESULT,
    MessageType.EXTENSION_CONFIG_REQUIRED,
    MessageType.EXTENSION_CONFIG_SAVED,
    MessageType.SESSION_CHANNELS,
    MessageType.SESSION_CHANNEL_SESSIONS,
    MessageType.SESSION_DETAIL,
    MessageType.SESSION_MESSAGES,
    MessageType.SESSION_INSTANCE_DELETED,
    MessageType.SESSION_CREATED,
    MessageType.SESSION_ACTIVE_SET,
    MessageType.WORKSPACE_LIST_RESULT,
    MessageType.WORKSPACE_READ_RESULT,
    MessageType.WORKSPACE_WRITE_RESULT,
    MessageType.WORKSPACE_DELETE_RESULT,
    MessageType.WORKSPACE_MKDIR_RESULT,
    MessageType.WORKSPACE_RENAME_RESULT,
    MessageType.WORKSPACE_ROOT,
    MessageType.CRON_JOBS,
    MessageType.CRON_JOB_ADDED,
    MessageType.CRON_JOB_DELETED,
    MessageType.CRON_JOB_TOGGLED,
    MessageType.CRON_JOB_RUN,
    MessageType.AGENT_LIST,
    MessageType.AGENT_SOUL,
    MessageType.AGENT_SAVED,
    MessageType.AGENT_DELETED,
    MessageType.AGENT_SYSTEM_FILES,
    MessageType.AGENT_SYSTEM_FILE,
    MessageType.AGENT_SYSTEM_FILE_SAVED,
    MessageType.IMAGE_UPLOADED,
    MessageType.IMAGE_ANALYSIS_RESULT,
    MessageType.IMAGE_GENERATED,
    MessageType.IMAGE_GENERATION_PROGRESS,
    MessageType.IMAGE_UNDERSTANDING_PROVIDERS,
    MessageType.IMAGE_GENERATION_PROVIDERS,
    MessageType.IMAGE_PROVIDER_ADDED,
    MessageType.IMAGE_PROVIDER_UPDATED,
    MessageType.IMAGE_PROVIDER_DELETED,
    # Agent Defaults
    MessageType.AGENT_DEFAULTS,
    MessageType.AGENT_DEFAULTS_UPDATED,
    MessageType.ENABLED_MODELS,
    # Channel
    MessageType.CHANNEL_LIST,
    MessageType.CHANNEL_UPDATED,
    MessageType.CHANNEL_DELETED,
    # Tool
    MessageType.TOOL_CONFIG,
    MessageType.TOOL_UPDATED,
    # Image Provider
    MessageType.IMAGE_PROVIDERS,
    MessageType.IMAGE_DEFAULT_PROVIDER_UPDATED,
}