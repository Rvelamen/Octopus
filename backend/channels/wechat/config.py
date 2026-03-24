"""WeChat channel configuration."""

from typing import Any


class WechatInnerConfig:
    """Inner configuration for WeChat ClawBot."""

    def __init__(
        self,
        appid: str = "",
        bot_token: str = "",
        allow_from: list[str] | None = None,
        context_tokens: dict[str, str] | None = None,
    ):
        self.appid = appid
        self.bot_token = bot_token
        self.allow_from = allow_from or []
        self.context_tokens = context_tokens or {}


class WechatConfig:
    """Configuration for WechatChannel."""

    def __init__(self, enabled: bool = False, config: WechatInnerConfig | None = None):
        self.enabled = enabled
        self.config = config or WechatInnerConfig()


def get_wechat_config(**kwargs: Any) -> WechatConfig:
    """Create WechatConfig with custom settings."""
    inner = WechatInnerConfig(
        appid=kwargs.get("appid", ""),
        bot_token=kwargs.get("bot_token", ""),
        allow_from=kwargs.get("allow_from", []),
        context_tokens=kwargs.get("context_tokens", {}),
    )
    return WechatConfig(enabled=kwargs.get("enabled", False), config=inner)
