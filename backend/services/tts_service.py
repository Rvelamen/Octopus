"""TTS service for managing TTS configuration and synthesis."""

from typing import Any

from loguru import logger

from backend.data.provider_store import ProviderRepository, SettingsRepository
from backend.data.session_store import SessionRepository
from backend.services.tts.base import TTSProvider, TTSResult, TTSVoice
from backend.services.tts.factory import TTSFactory
from backend.utils.helpers import get_data_path


class TTSService:
    """Service for TTS operations."""
    
    DEFAULT_TTS_CONFIG = {
        "provider": "mimo",
        "providerId": None,
        "voice": "mimo_default",
        "format": "wav",
        "defaultStyle": None,
    }
    
    def __init__(self, session_db: SessionRepository, provider_repo: ProviderRepository, settings_repo: SettingsRepository = None):
        """Initialize TTS service.
        
        Args:
            session_db: Session repository for TTS config storage
            provider_repo: Provider repository for API credentials
            settings_repo: Settings repository for global defaults
        """
        self.session_db = session_db
        self.provider_repo = provider_repo
        self.settings_repo = settings_repo if settings_repo else None
    
    def get_instance_tts_config(self, instance_id: int) -> dict[str, Any]:
        """Get TTS config for a session instance."""
        instance = self.session_db.get_instance_by_id(instance_id)
        if not instance:
            logger.warning(f"[TTSService] Instance {instance_id} not found")
            return {"enabled": False, "config": self.DEFAULT_TTS_CONFIG.copy()}
        
        config = instance.tts_config or {}
        merged_config = {**self.DEFAULT_TTS_CONFIG, **config}
        
        result = {
            "enabled": getattr(instance, 'tts_enabled', False) or False,
            "config": merged_config
        }
        logger.debug(f"[TTSService] get_instance_tts_config({instance_id}): {result}")
        
        return result
    
    def update_instance_tts_config(
        self,
        instance_id: int,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None
    ) -> bool:
        """Update TTS config for a session instance."""
        return self.session_db.update_instance_tts_config(instance_id, enabled, config)
    
    def get_global_defaults(self) -> dict[str, Any]:
        """Get global default TTS config."""
        defaults = self.DEFAULT_TTS_CONFIG.copy()
        
        if self.settings_repo:
            settings = self.settings_repo.get_all_settings()
            
            if "tts_default_provider" in settings:
                defaults["provider"] = settings["tts_default_provider"]
            if "tts_default_voice" in settings:
                defaults["voice"] = settings["tts_default_voice"]
            if "tts_default_format" in settings:
                defaults["format"] = settings["tts_default_format"]
            if "tts_default_style" in settings:
                defaults["defaultStyle"] = settings["tts_default_style"]
            if "tts_default_provider_id" in settings:
                defaults["providerId"] = settings["tts_default_provider_id"]
        
        return defaults
    
    def set_global_defaults(self, defaults: dict[str, Any]) -> bool:
        """Set global default TTS config."""
        try:
            if not self.settings_repo:
                return False
                
            if "provider" in defaults:
                self.settings_repo.set_setting("tts_default_provider", defaults["provider"])
            if "voice" in defaults:
                self.settings_repo.set_setting("tts_default_voice", defaults["voice"])
            if "format" in defaults:
                self.settings_repo.set_setting("tts_default_format", defaults["format"])
            if "defaultStyle" in defaults:
                self.settings_repo.set_setting("tts_default_style", defaults["defaultStyle"])
            if "providerId" in defaults:
                self.settings_repo.set_setting("tts_default_provider_id", str(defaults["providerId"]))
            return True
        except Exception as e:
            logger.error(f"Failed to set global TTS defaults: {e}")
            return False
    
    def get_provider(self, config: dict[str, Any]) -> TTSProvider:
        """Create a TTS provider instance from config."""
        provider_type = config.get("provider", "mimo")
        provider_id = config.get("providerId")
        
        provider_record = None
        if provider_id:
            provider_record = self.provider_repo.get_provider_by_id(int(provider_id))
        
        if not provider_record:
            provider_record = self._find_compatible_provider(provider_type)
        
        if not provider_record:
            raise ValueError(f"No compatible provider found for TTS type: {provider_type}")
        
        return TTSFactory.create(provider_type, provider_record)
    
    def _find_compatible_provider(self, provider_type: str):
        """Find a compatible provider for the given TTS type."""
        providers = self.provider_repo.get_all_providers()
        
        for provider in providers:
            if not provider.enabled:
                continue
            
            if provider_type == "mimo":
                if provider.api_host and "mimo" in provider.api_host.lower():
                    return provider
                if "mimo" in provider.name.lower():
                    return provider
            elif provider_type == "openai":
                if provider.provider_type == "openai":
                    return provider
        
        for provider in providers:
            if provider.enabled and provider.provider_type == "openai":
                return provider
        
        return None
    
    async def synthesize(
        self,
        text: str,
        config: dict[str, Any],
        style: str = None
    ) -> TTSResult:
        """Synthesize text to speech."""
        provider = self.get_provider(config)
        
        voice = config.get("voice")
        model = config.get("model")
        format = config.get("format", "wav")
        use_style = style or config.get("defaultStyle")
        
        return await provider.synthesize(
            text=text,
            voice=voice,
            model=model,
            style=use_style,
            format=format
        )
    
    def get_available_voices(self, provider_type: str) -> list[TTSVoice]:
        """Get available voices for a provider type."""
        try:
            provider = TTSFactory.create(provider_type, self._find_compatible_provider(provider_type))
            return provider.get_available_voices()
        except Exception:
            if provider_type == "mimo":
                from backend.services.tts.mimo_tts import MiMoTTS
                return MiMoTTS.VOICES.copy()
            elif provider_type == "openai":
                from backend.services.tts.openai_tts import OpenAITTS
                return OpenAITTS.VOICES.copy()
        return []
    
    def get_available_styles(self, provider_type: str) -> list[dict]:
        """Get available styles for a provider type."""
        if provider_type == "mimo":
            from backend.services.tts.mimo_tts import MiMoTTS
            return MiMoTTS.SUPPORTED_STYLES.copy()
        return []
    
    @staticmethod
    def get_supported_providers() -> list[dict]:
        """Get list of supported TTS providers."""
        return TTSFactory.get_supported_providers()
