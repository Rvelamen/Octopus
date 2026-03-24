"""WeChat ClawBot channel implementation."""

from backend.channels.wechat.channel import WechatChannel
from backend.channels.wechat.config import WechatConfig, get_wechat_config

__all__ = ["WechatChannel", "WechatConfig", "get_wechat_config"]
