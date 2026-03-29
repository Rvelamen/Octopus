"""TTS provider factory."""

from typing import TYPE_CHECKING

from loguru import logger

from backend.services.tts.base import TTSProvider

if TYPE_CHECKING:
    from backend.data.provider_store import ProviderRecord


class TTSFactory:
    """Factory for creating TTS providers."""
    
    SUPPORTED_PROVIDERS = {
        "openai": {
            "name": "OpenAI TTS",
            "requires_provider": True,
            "supports_style": False,
            "supports_stream": True,
        },
        "mimo": {
            "name": "MiMo TTS",
            "requires_provider": True,
            "supports_style": True,
            "supports_stream": True,
            "base_url": "https://api.xiaomimimo.com/v1",
        },
    }
    
    @staticmethod
    def create(provider_type: str, provider_record: "ProviderRecord" = None) -> TTSProvider:
        """Create a TTS provider instance.
        
        Args:
            provider_type: Type of TTS provider (openai, mimo)
            provider_record: Provider record with API credentials
            
        Returns:
            TTSProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type == "openai":
            from backend.services.tts.openai_tts import OpenAITTS
            
            if not provider_record:
                raise ValueError("OpenAI TTS requires a provider record with API key")
            
            return OpenAITTS(
                api_key=provider_record.api_key,
                base_url=provider_record.api_host or None
            )
        
        elif provider_type == "mimo":
            from backend.services.tts.mimo_tts import MiMoTTS
            
            if not provider_record:
                raise ValueError("MiMo TTS requires a provider record with API key")
            
            base_url = provider_record.api_host or "https://api.xiaomimimo.com/v1"
            
            return MiMoTTS(
                api_key=provider_record.api_key,
                base_url=base_url
            )
        
        raise ValueError(f"Unsupported TTS provider: {provider_type}")
    
    @staticmethod
    def get_supported_providers() -> list[dict]:
        """Get list of supported TTS providers.
        
        Returns:
            List of provider info dicts
        """
        return [
            {"id": k, **v}
            for k, v in TTSFactory.SUPPORTED_PROVIDERS.items()
        ]
    
    @staticmethod
    def get_provider_info(provider_type: str) -> dict | None:
        """Get info about a specific provider.
        
        Args:
            provider_type: Type of TTS provider
            
        Returns:
            Provider info dict or None if not found
        """
        info = TTSFactory.SUPPORTED_PROVIDERS.get(provider_type)
        if info:
            return {"id": provider_type, **info}
        return None
