"""Channel manager for coordinating chat channels."""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from backend.core.events.types import OutboundMessage
from backend.core.events.bus import MessageBus
from backend.channels.base import BaseChannel


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels
    - Start/stop channels
    - Route outbound messages
    """

    _global_instance = None

    def __init__(self, bus: MessageBus, workspace: Path | None = None, custom_channels: dict[str, BaseChannel] | None = None):
        self.bus = bus
        self.workspace = workspace
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None

        self._init_channels()

        if custom_channels:
            self.channels.update(custom_channels)
            logger.info(f"Added {len(custom_channels)} custom channels")
        
        ChannelManager._global_instance = self
    
    @classmethod
    def _get_global_instance(cls):
        """Get the global ChannelManager instance."""
        return cls._global_instance
    
    def _init_channels(self) -> None:
        """Initialize channels based on database config."""

        db_channel_configs = {}
        try:
            from backend.data import Database
            from backend.data.provider_store import ChannelConfigRepository

            db = Database()
            repo = ChannelConfigRepository(db)
            all_configs = repo.get_all_channel_configs()
            for cfg in all_configs:
                db_channel_configs[cfg.channel_name] = cfg
            logger.info(f"Loaded {len(db_channel_configs)} channel configs from database")
        except Exception as e:
            logger.warning(f"Failed to load channel configs from database: {e}")
            return

        feishu_config = db_channel_configs.get("feishu")
        if feishu_config and feishu_config.enabled:
            try:
                from backend.channels.feishu.channel import FeishuChannel
                from backend.core.config.schema import FeishuConfig, FeishuInnerConfig

                inner = FeishuInnerConfig(
                    app_id=feishu_config.app_id,
                    app_secret=feishu_config.app_secret,
                    encrypt_key=feishu_config.encrypt_key,
                    verification_token=feishu_config.verification_token,
                    allow_from=feishu_config.allow_from,
                )
                channel_config = FeishuConfig(enabled=True, config=inner)

                self.channels["feishu"] = FeishuChannel(
                    channel_config, self.bus, self.workspace
                )
                logger.info("Feishu channel initialized")
            except ImportError as e:
                logger.warning(f"Feishu channel not available: {e}")
        
        wechat_config = db_channel_configs.get("wechat")
        if wechat_config and wechat_config.enabled:
            try:
                from backend.channels.wechat.channel import WechatChannel
                from backend.core.config.schema import WechatConfig, WechatInnerConfig

                inner = WechatInnerConfig(
                    appid=wechat_config.app_id,
                    bot_token=wechat_config.app_secret,
                    allow_from=wechat_config.allow_from,
                )
                channel_config = WechatConfig(enabled=True, config=inner)

                self.channels["wechat"] = WechatChannel(channel_config, self.bus)
                logger.info("WeChat channel initialized")
            except ImportError as e:
                logger.warning(f"WeChat channel not available: {e}")

        # --- New channels initialized from config_json ---
        self._init_generic_channel(db_channel_configs, "telegram", "backend.channels.telegram.channel", "TelegramChannel", "backend.core.config.schema", "TelegramConfig", "TelegramInnerConfig")
        self._init_generic_channel(db_channel_configs, "dingtalk", "backend.channels.dingtalk.channel", "DingTalkChannel", "backend.core.config.schema", "DingTalkConfig", "DingTalkInnerConfig")
        self._init_generic_channel(db_channel_configs, "slack", "backend.channels.slack.channel", "SlackChannel", "backend.core.config.schema", "SlackConfig", "SlackInnerConfig")
        self._init_generic_channel(db_channel_configs, "discord", "backend.channels.discord.channel", "DiscordChannel", "backend.core.config.schema", "DiscordConfig", "DiscordInnerConfig")
        self._init_generic_channel(db_channel_configs, "email", "backend.channels.email.channel", "EmailChannel", "backend.core.config.schema", "EmailConfig", "EmailInnerConfig")

    def _init_generic_channel(
        self,
        db_channel_configs: dict,
        channel_name: str,
        module_path: str,
        class_name: str,
        schema_module: str,
        config_class: str,
        inner_class: str,
    ) -> None:
        """Initialize a generic channel from DB config using config_json."""
        cfg = db_channel_configs.get(channel_name)
        if not cfg or not cfg.enabled:
            return
        try:
            channel_module = __import__(module_path, fromlist=[class_name])
            ChannelClass = getattr(channel_module, class_name)
            schema_mod = __import__(schema_module, fromlist=[config_class, inner_class])
            ConfigClass = getattr(schema_mod, config_class)
            InnerClass = getattr(schema_mod, inner_class)

            config_json = cfg.config_json if isinstance(cfg.config_json, dict) else {}
            inner = InnerClass(**config_json, allow_from=cfg.allow_from)
            channel_config = ConfigClass(enabled=True, config=inner)

            self.channels[channel_name] = ChannelClass(channel_config, self.bus)
            logger.info(f"{channel_name.capitalize()} channel initialized")
        except ImportError as e:
            logger.warning(f"{channel_name} channel not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize {channel_name} channel: {e}")

    def ensure_channel(self, channel_name: str) -> bool:
        """Ensure a channel is initialized and ready to start."""
        if channel_name in self.channels:
            return True

        try:
            from backend.data import Database
            from backend.data.provider_store import ChannelConfigRepository

            db = Database()
            repo = ChannelConfigRepository(db)
            config = repo.get_channel_config(channel_name)

            if not config or not config.enabled:
                logger.warning(f"Channel {channel_name} is not enabled")
                return False

            if channel_name == "wechat":
                from backend.channels.wechat.channel import WechatChannel
                from backend.core.config.schema import WechatConfig, WechatInnerConfig

                inner = WechatInnerConfig(
                    appid=config.app_id,
                    bot_token=config.app_secret,
                    allow_from=config.allow_from,
                )
                channel_config = WechatConfig(enabled=True, config=inner)
                self.channels[channel_name] = WechatChannel(channel_config, self.bus)
                logger.info(f"Channel {channel_name} dynamically added")
                return True

            # Generic channel ensure for new channels
            generic_channels = {
                "telegram": ("backend.channels.telegram.channel", "TelegramChannel", "TelegramConfig", "TelegramInnerConfig"),
                "dingtalk": ("backend.channels.dingtalk.channel", "DingTalkChannel", "DingTalkConfig", "DingTalkInnerConfig"),
                "slack": ("backend.channels.slack.channel", "SlackChannel", "SlackConfig", "SlackInnerConfig"),
                "discord": ("backend.channels.discord.channel", "DiscordChannel", "DiscordConfig", "DiscordInnerConfig"),
                "email": ("backend.channels.email.channel", "EmailChannel", "EmailConfig", "EmailInnerConfig"),
            }

            if channel_name in generic_channels:
                mod_path, cls_name, cfg_name, inner_name = generic_channels[channel_name]
                channel_module = __import__(mod_path, fromlist=[cls_name])
                ChannelClass = getattr(channel_module, cls_name)
                from backend.core.config.schema import (
                    TelegramConfig, TelegramInnerConfig,
                    DingTalkConfig, DingTalkInnerConfig,
                    SlackConfig, SlackInnerConfig,
                    DiscordConfig, DiscordInnerConfig,
                    EmailConfig, EmailInnerConfig,
                )
                schema_map = {
                    "telegram": (TelegramConfig, TelegramInnerConfig),
                    "dingtalk": (DingTalkConfig, DingTalkInnerConfig),
                    "slack": (SlackConfig, SlackInnerConfig),
                    "discord": (DiscordConfig, DiscordInnerConfig),
                    "email": (EmailConfig, EmailInnerConfig),
                }
                ConfigClass, InnerClass = schema_map[channel_name]
                config_json = config.config_json if isinstance(config.config_json, dict) else {}
                inner = InnerClass(**config_json, allow_from=config.allow_from)
                channel_config = ConfigClass(enabled=True, config=inner)
                self.channels[channel_name] = ChannelClass(channel_config, self.bus)
                logger.info(f"Channel {channel_name} dynamically added")
                return True

        except Exception as e:
            logger.error(f"Failed to ensure channel {channel_name}: {e}")
        return False

    async def start_channel(self, channel_name: str) -> bool:
        """Start a specific channel if not already running."""
        logger.info(f"start_channel called for {channel_name}")
        if channel_name not in self.channels:
            logger.info(f"Channel {channel_name} not found, calling ensure_channel")
            if not self.ensure_channel(channel_name):
                return False

        channel = self.channels[channel_name]
        logger.info(f"Found channel {channel_name}: {channel}")
        if hasattr(channel, '_running') and channel._running:
            logger.info(f"Channel {channel_name} already running")
            return True

        try:
            logger.info(f"Creating task to start channel {channel_name}")
            task = asyncio.create_task(channel.start())
            if hasattr(channel, '_poll_task'):
                channel._poll_task = task
            logger.info(f"Started channel {channel_name}, task: {task}")
            return True
        except Exception as e:
            logger.error(f"Failed to start channel {channel_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        return False

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return
        
        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())
        
        # Start all channels
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            tasks.append(asyncio.create_task(channel.start()))
        
        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")
        
        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        
        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")
    
    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")
        
        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )
                
                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Unknown channel: {msg.channel}")
                    
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)
    
    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }
    
    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
