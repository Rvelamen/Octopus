"""Models handler for Desktop channel.

This module contains the GetModelsHandler class for fetching available models
from various AI providers.
"""

import asyncio
import json
import uuid
import time
from typing import Any

from fastapi import WebSocket
from loguru import logger

from backend.channels.desktop.protocol import MessageType, WSMessage
from backend.channels.desktop.handlers.base import MessageHandler
from backend.data import Database
from backend.data.provider_store import ProviderRepository


class GetModelsHandler(MessageHandler):
    """Handle get models requests."""

    def __init__(self, bus, db: Database = None):
        super().__init__(bus)
        self.db = db or Database()
        self.provider_repo = ProviderRepository(self.db)

    async def handle(self, websocket: WebSocket, message: WSMessage) -> None:
        """Return available models for a provider."""
        provider_name = message.data.get("provider")

        if not provider_name:
            await self._send_error(websocket, message.request_id, "Provider name is required")
            return

        try:
            models = await self._fetch_models_from_provider(provider_name)
        except Exception as e:
            logger.error(f"Failed to fetch models for {provider_name}: {e}")
            models = []

        await self.send_response(websocket, WSMessage(
            type=MessageType.MODELS,
            request_id=message.request_id,
            data={
                "provider": provider_name,
                "models": models
            }
        ))

    async def _fetch_models_from_provider(self, provider_name: str) -> list[dict]:
        """Fetch models from provider's API using database config."""
        provider_record = self.provider_repo.get_provider_by_name(provider_name)
        if not provider_record:
            logger.warning(f"Provider not found: {provider_name}")
            return []

        api_key = provider_record.api_key
        api_base = provider_record.api_host
        provider_type = provider_record.provider_type

        if not api_key:
            logger.warning(f"No API key found for provider: {provider_name}")
            return []

        if provider_type == "anthropic":
            return await self._fetch_anthropic_models(api_key)
        elif provider_type == "openai":
            return await self._fetch_openai_models(api_key, api_base)
        elif provider_type == "deepseek":
            return await self._fetch_deepseek_models(api_key, api_base)
        elif provider_type == "openrouter":
            return await self._fetch_openrouter_models(api_key)
        elif provider_type == "groq":
            return await self._fetch_groq_models(api_key)
        elif provider_type == "zhipu":
            return await self._fetch_zhipu_models(api_key, api_base)
        elif provider_type == "gemini":
            return await self._fetch_gemini_models(api_key)
        elif provider_type == "minimax":
            return await self._fetch_minimax_models(api_key, api_base)
        elif provider_type == "minimax-coding-plan":
            return await self._fetch_minimax_coding_plan_models()
        elif provider_type == "kimi":
            return await self._fetch_kimi_models(api_key, api_base)
        else:
            logger.warning(f"Unknown provider type: {provider_type}")
            return []

    async def _fetch_anthropic_models(self, api_key: str) -> list[dict]:
        """Fetch models from Anthropic API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01"
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["display_name"] or m["id"]}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"Anthropic API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Anthropic models: {e}")
            return []

    async def _fetch_openai_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from OpenAI API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.openai.com/v1"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                logger.info(f"OpenAI API response: {response.status_code} {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["id"]}
                        for m in data.get("data", [])
                        if "gpt" in m["id"].lower() or "o1" in m["id"].lower() or "o3" in m["id"].lower()
                    ]
                else:
                    logger.error(f"OpenAI API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch OpenAI models: {e}")
            return []

    async def _fetch_deepseek_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from DeepSeek API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.deepseek.com/v1"
            logger.info(f"DeepSeek API base URL: {base_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                logger.info(f"DeepSeek API response: {response.status_code} {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["id"]}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"DeepSeek API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch DeepSeek models: {e}")
            return []

    async def _fetch_openrouter_models(self, api_key: str) -> list[dict]:
        """Fetch models from OpenRouter API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": f"{m.get('name', m['id'])} (OpenRouter)"}
                        for m in data.get("data", [])[:50]
                    ]
                else:
                    logger.error(f"OpenRouter API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter models: {e}")
            return []

    async def _fetch_groq_models(self, api_key: str) -> list[dict]:
        """Fetch models from Groq API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m["id"]}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"Groq API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Groq models: {e}")
            return []

    async def _fetch_zhipu_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from Zhipu (智谱) API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://open.bigmodel.cn/api/paas/v4"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m.get("name", m["id"])}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"Zhipu API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Zhipu models: {e}")
            return []

    async def _fetch_gemini_models(self, api_key: str) -> list[dict]:
        """Fetch models from Google Gemini API."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["name"].split("/")[-1], "label": m.get("displayName", m["name"].split("/")[-1])}
                        for m in data.get("models", [])
                    ]
                else:
                    logger.error(f"Gemini API error: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch Gemini models: {e}")
            return []

    async def _fetch_minimax_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from MiniMax API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.minimax.chat/v1"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m.get("name", m["id"])}
                        for m in data.get("data", [])
                    ]
                else:
                    logger.error(f"MiniMax API error: {response.status_code} {response.text}")
                    return [

                    ]
        except Exception as e:
            logger.error(f"Failed to fetch MiniMax models: {e}")
            return []

    async def _fetch_minimax_coding_plan_models(self) -> list[dict]:
        """Return fixed models for MiniMax Coding Plan.

        Coding Plan supports the following text models:
        - MiniMax-M2.5
        - MiniMax-M2.1
        - MiniMax-M2
        - MiniMax-M2.5-highspeed (high-speed version)

        These models cannot be fetched via API, so we return them directly.
        """
        return [
            {"value": "MiniMax-M2.5", "label": "MiniMax-M2.5"},
            {"value": "MiniMax-M2.1", "label": "MiniMax-M2.1"},
            {"value": "MiniMax-M2", "label": "MiniMax-M2"},
            {"value": "MiniMax-M2.5-highspeed", "label": "MiniMax-M2.5-highspeed (极速版)"}
        ]

    async def _fetch_kimi_models(self, api_key: str, api_base: str) -> list[dict]:
        """Fetch models from Kimi (Moonshot) API."""
        import httpx
        try:
            base_url = api_base.rstrip("/") if api_base else "https://api.moonshot.cn/v1"
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {"value": m["id"], "label": m.get("display_name", m["id"])}
                        for m in data.get("data", [])
                        # {"value": "k2p5", "label": "kimi-for-coding"}
                    ]
                else:
                    logger.error(f"Kimi API error: {response.status_code} {response.text}")
                    return [
                        {"value": "kimi-for-coding", "label": "kimi-for-coding"}
                    ]
        except Exception as e:
            logger.error(f"Failed to fetch Kimi models: {e}")
            return []

    async def _send_error(self, websocket: WebSocket, request_id: str | None, error: str) -> None:
        """Send error response."""
        await self.send_response(websocket, WSMessage(
            type=MessageType.ERROR,
            request_id=request_id,
            data={"error": error}
        ))
