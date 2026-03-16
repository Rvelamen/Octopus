"""Image service for understanding and generation."""

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from backend.data.database import Database


@dataclass
class ImageProviderInfo:
    """Image provider info from AI provider config."""
    name: str
    provider_type: str
    api_key: str
    api_base: str
    model: str
    is_default: bool
    enabled: bool


class ImageService:
    """Service for image understanding and generation."""

    # Provider type mapping: AI provider type -> image capability (基于图片中的8种类型)
    UNDERSTANDING_PROVIDER_TYPES = {'openai', 'openai-response', 'gemini', 'anthropic', 'azure-openai', 'new-api', 'cherryln', 'ollama'}
    GENERATION_PROVIDER_TYPES = {'openai', 'openai-response', 'azure-openai', 'new-api', 'cherryln'}

    # Default models for image understanding by provider type
    DEFAULT_UNDERSTANDING_MODELS = {
        'openai': 'gpt-4o',
        'openai-response': 'gpt-4o',
        'gemini': 'gemini-pro-vision',
        'anthropic': 'claude-3-opus-4-5',
        'azure-openai': 'gpt-4o',
        'new-api': 'gpt-4o',
        'cherryln': 'gpt-4o',
        'ollama': 'llava'
    }

    # Default models for image generation by provider type
    DEFAULT_GENERATION_MODELS = {
        'openai': 'dall-e-3',
        'openai-response': 'dall-e-3',
        'azure-openai': 'dall-e-3',
        'new-api': 'dall-e-3',
        'cherryln': 'dall-e-3'
    }

    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self._image_repo = None

    def _get_image_repo(self):
        """Get image service config repository."""
        if self._image_repo is None:
            from backend.data.provider_store import ImageServiceConfigRepository
            self._image_repo = ImageServiceConfigRepository(self.db)
        return self._image_repo

    # ========== Provider Management (Database-based) ==========

    def get_available_understanding_models(self) -> list[dict]:
        """Get available understanding models from enabled providers."""
        return self._get_image_repo().get_available_models('understanding')

    def get_available_generation_models(self) -> list[dict]:
        """Get available generation models from enabled providers."""
        return self._get_image_repo().get_available_models('generation')

    def get_default_understanding_model(self) -> dict | None:
        """Get the default understanding model from database."""
        return self._get_image_repo().get_default_model('understanding')

    def get_default_generation_model(self) -> dict | None:
        """Get the default generation model from database."""
        return self._get_image_repo().get_default_model('generation')

    # ========== Image Understanding ==========

    async def understand_image(self, image_path: str, question: str = "",
                                model_id: int | None = None) -> str:
        """Understand an image using the specified or default model."""
        if model_id:
            # Get specific model from available models
            models = self.get_available_understanding_models()
            model_info = next((m for m in models if m["modelDbId"] == model_id), None)
            if not model_info:
                raise ValueError(f"Model not found: {model_id}")
        else:
            model_info = self.get_default_understanding_model()
            if not model_info:
                raise ValueError("No image understanding model configured")

        provider_type = model_info["providerType"].lower()
        api_key = model_info["apiKey"]
        api_base = model_info.get("apiHost", "")
        model = model_info.get("modelId") or self.DEFAULT_UNDERSTANDING_MODELS.get(provider_type, "")

        if not api_key:
            raise ValueError(f"Provider {provider['provider_name']} has no API key")

        # Read and encode image
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path_obj, "rb") as f:
            image_data = f.read()

        ext = image_path_obj.suffix.lstrip(".").lower()
        if ext == "jpg":
            ext = "jpeg"

        base64_image = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:image/{ext};base64,{base64_image}"

        # Call provider-specific implementation
        if provider_type == "kimi":
            return await self._understand_with_kimi(api_key, api_base, image_url, question, model)
        elif provider_type == "openai":
            return await self._understand_with_openai(api_key, api_base, image_url, question, model)
        elif provider_type == "anthropic":
            return await self._understand_with_anthropic(api_key, api_base, image_url, question, model)
        elif provider_type == "gemini":
            return await self._understand_with_gemini(api_key, api_base, image_url, question, model)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

    async def _understand_with_kimi(self, api_key: str, api_base: str,
                                     image_url: str, question: str, model: str) -> str:
        """Understand image using Kimi API."""
        base_url = api_base or "https://api.moonshot.cn/v1"

        messages = [
            {"role": "system", "content": "你是 Kimi，一个能够理解和分析图片的AI助手。"},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": question or "请详细描述这张图片的内容。"},
                ],
            },
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _understand_with_openai(self, api_key: str, api_base: str,
                                       image_url: str, question: str, model: str) -> str:
        """Understand image using OpenAI API."""
        base_url = api_base or "https://api.openai.com/v1"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": question or "请详细描述这张图片的内容。"},
                ],
            },
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.3,
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _understand_with_anthropic(self, api_key: str, api_base: str,
                                          image_url: str, question: str, model: str) -> str:
        """Understand image using Anthropic Claude API."""
        base_url = api_base or "https://api.anthropic.com/v1"

        # Extract base64 data from data URL
        base64_data = image_url.split(",")[1]
        media_type = image_url.split(";")[0].split(":")[1]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_data,
                                    },
                                },
                                {"type": "text", "text": question or "请详细描述这张图片的内容。"},
                            ],
                        },
                    ],
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def _understand_with_gemini(self, api_key: str, api_base: str,
                                       image_url: str, question: str, model: str) -> str:
        """Understand image using Google Gemini API."""
        base_url = api_base or "https://generativelanguage.googleapis.com/v1beta"

        # Extract base64 data
        base64_data = image_url.split(",")[1]
        mime_type = image_url.split(";")[0].split(":")[1]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/models/{model}:generateContent?key={api_key}",
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": question or "请详细描述这张图片的内容。"},
                                {
                                    "inline_data": {
                                        "mime_type": mime_type,
                                        "data": base64_data
                                    }
                                }
                            ]
                        }
                    ]
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    # ========== Image Generation ==========

    async def generate_image(self, prompt: str, size: str | None = None,
                              quality: str | None = None,
                              model_id: int | None = None) -> dict[str, Any]:
        """Generate an image using the specified or default model."""
        if model_id:
            models = self.get_available_generation_models()
            model_info = next((m for m in models if m["modelDbId"] == model_id), None)
            if not model_info:
                raise ValueError(f"Model not found: {model_id}")
        else:
            model_info = self.get_default_generation_model()
            if not model_info:
                raise ValueError("No image generation model configured")

        provider_type = model_info["providerType"].lower()
        api_key = model_info["apiKey"]
        api_base = model_info.get("apiHost", "")
        model = model_info.get("modelId") or self.DEFAULT_GENERATION_MODELS.get(provider_type, "")
        default_size = model_info.get("defaultSize", "1024x1024")
        default_quality = model_info.get("defaultQuality", "standard")

        if not api_key:
            raise ValueError(f"Provider {provider['provider_name']} has no API key")

        size = size or default_size
        quality = quality or default_quality

        if provider_type == "openai":
            return await self._generate_with_dalle(api_key, api_base, prompt, size, quality, model)
        elif provider_type == "stability":
            return await self._generate_with_stability(api_key, prompt, size)
        else:
            raise ValueError(f"Unsupported generation provider type: {provider_type}")

    async def _generate_with_dalle(self, api_key: str, api_base: str,
                                    prompt: str, size: str, quality: str, model: str) -> dict[str, Any]:
        """Generate image using DALL-E API."""
        base_url = api_base or "https://api.openai.com/v1"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/images/generations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "quality": quality,
                    "n": 1,
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            return {
                "url": data["data"][0]["url"],
                "revised_prompt": data["data"][0].get("revised_prompt", prompt),
            }

    async def _generate_with_stability(self, api_key: str, prompt: str, size: str) -> dict[str, Any]:
        """Generate image using Stability AI API."""
        # Parse size (e.g., "1024x1024" -> 1024, 1024)
        width, height = map(int, size.split("x"))

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.stability.ai/v2beta/stable-image/generate/sd3",
                headers={"Authorization": f"Bearer {api_key}"},
                data={
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                },
                timeout=60.0,
            )

            response.raise_for_status()
            data = response.json()
            return {
                "url": data["image_url"],
                "revised_prompt": prompt,
            }
