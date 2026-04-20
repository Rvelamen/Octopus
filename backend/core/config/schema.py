"""Configuration schema using Pydantic."""

from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from backend.mcp.config import MCPConfig


class FeishuInnerConfig(BaseModel):
    """Inner config for Feishu/Lark channel (camelCase for JSON config)."""
    app_id: str = Field(default="", alias="appId")
    app_secret: str = Field(default="", alias="appSecret")
    encrypt_key: str = Field(default="", alias="encryptKey")
    verification_token: str = Field(default="", alias="verificationToken")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")

    class Config:
        populate_by_name = True


class FeishuConfig(BaseModel):
    """Feishu/Lark channel configuration using WebSocket long connection."""
    enabled: bool = False
    config: FeishuInnerConfig = Field(default_factory=FeishuInnerConfig)


class WechatInnerConfig(BaseModel):
    """Inner config for WeChat ClawBot channel (camelCase for JSON config)."""
    appid: str = ""
    bot_token: str = Field(default="", alias="botToken")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    context_tokens: dict[str, str] = Field(default_factory=dict, alias="contextTokens")

    class Config:
        populate_by_name = True


class WechatConfig(BaseModel):
    """WeChat ClawBot channel configuration using HTTP long polling."""
    enabled: bool = False
    config: WechatInnerConfig = Field(default_factory=WechatInnerConfig)


class TelegramInnerConfig(BaseModel):
    """Inner config for Telegram channel."""
    token: str = ""
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    class Config:
        populate_by_name = True

class TelegramConfig(BaseModel):
    enabled: bool = False
    config: TelegramInnerConfig = Field(default_factory=TelegramInnerConfig)

class DingTalkInnerConfig(BaseModel):
    """Inner config for DingTalk channel."""
    client_id: str = Field(default="", alias="clientId")
    client_secret: str = Field(default="", alias="clientSecret")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    class Config:
        populate_by_name = True

class DingTalkConfig(BaseModel):
    enabled: bool = False
    config: DingTalkInnerConfig = Field(default_factory=DingTalkInnerConfig)

class SlackInnerConfig(BaseModel):
    """Inner config for Slack channel."""
    bot_token: str = Field(default="", alias="botToken")
    app_token: str = Field(default="", alias="appToken")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    class Config:
        populate_by_name = True

class SlackConfig(BaseModel):
    enabled: bool = False
    config: SlackInnerConfig = Field(default_factory=SlackInnerConfig)

class DiscordInnerConfig(BaseModel):
    """Inner config for Discord channel."""
    token: str = ""
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    class Config:
        populate_by_name = True

class DiscordConfig(BaseModel):
    enabled: bool = False
    config: DiscordInnerConfig = Field(default_factory=DiscordInnerConfig)

class EmailInnerConfig(BaseModel):
    """Inner config for Email channel."""
    imap_host: str = Field(default="imap.gmail.com", alias="imapHost")
    imap_port: int = Field(default=993, alias="imapPort")
    smtp_host: str = Field(default="smtp.gmail.com", alias="smtpHost")
    smtp_port: int = Field(default=587, alias="smtpPort")
    address: str = ""
    password: str = ""
    poll_interval: int = Field(default=15, alias="pollInterval")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    class Config:
        populate_by_name = True

class EmailConfig(BaseModel):
    enabled: bool = False
    config: EmailInnerConfig = Field(default_factory=EmailInnerConfig)

class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    wechat: WechatConfig = Field(default_factory=WechatConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    model_config = {"populate_by_name": True}

    workspace: str = ""
    model: str = "anthropic/claude-opus-4-5"
    provider: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7
    max_iterations: int = Field(default=20, alias="maxIterations")
    context_compression_enabled: bool = Field(default=False, alias="contextCompressionEnabled")
    context_compression_turns: int = Field(default=10, alias="contextCompressionTurns")
    context_compression_token_threshold: int = Field(default=100000, alias="contextCompressionTokenThreshold")
    compression_trigger_ratio: float = Field(default=0.60, alias="compressionTriggerRatio")
    compression_tail_token_budget: int = Field(default=15000, alias="compressionTailTokenBudget")
    llm_max_retries: int = Field(default=3, alias="llmMaxRetries")
    llm_retry_base_delay: float = Field(default=1.0, alias="llmRetryBaseDelay")
    llm_retry_max_delay: float = Field(default=30.0, alias="llmRetryMaxDelay")


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    type: str = "openai"
    api_key: str = ""
    api_base: str | None = None


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""
    timeout: int = 1800
    restrict_to_workspace: bool = True


class ToolsConfig(BaseModel):
    """Tools configuration."""
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)


class Config(BaseSettings):
    """Main configuration."""
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    
    model_config = {
        "extra": "ignore",
        "env_prefix": "OCTOPUS_",
        "env_nested_delimiter": "__"
    }
