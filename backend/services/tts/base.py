"""TTS base classes and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class TTSResult:
    """TTS synthesis result."""
    audio_data: bytes
    format: str
    duration_ms: int = 0


@dataclass
class TTSVoice:
    """TTS voice information."""
    id: str
    name: str
    gender: str = "neutral"
    language: str = "zh"


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = None,
        model: str = None,
        speed: float = 1.0,
        style: str = None,
        audio_tags: str = None
    ) -> TTSResult:
        """Synthesize text to speech.
        
        Args:
            text: Text to synthesize
            voice: Voice ID to use
            model: Model ID to use
            speed: Speech speed (0.25-4.0)
            style: Style for style control (e.g., "开心", "东北话")
            audio_tags: Fine-grained audio control tags
            
        Returns:
            TTSResult with audio data
        """
        pass
    
    async def synthesize_stream(
        self,
        text: str,
        voice: str = None,
        model: str = None,
        speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        """Stream synthesis (optional implementation).
        
        Args:
            text: Text to synthesize
            voice: Voice ID to use
            model: Model ID to use
            speed: Speech speed
            
        Yields:
            Audio data chunks
        """
        raise NotImplementedError("Stream synthesis not supported by this provider")
    
    @abstractmethod
    def get_available_voices(self) -> list[TTSVoice]:
        """Get list of available voices.
        
        Returns:
            List of TTSVoice objects
        """
        pass
    
    def supports_style_control(self) -> bool:
        """Check if provider supports style control.
        
        Returns:
            True if style control is supported
        """
        return False
    
    def supports_audio_tags(self) -> bool:
        """Check if provider supports audio tags.
        
        Returns:
            True if audio tags are supported
        """
        return False
    
    def get_supported_styles(self) -> list[str]:
        """Get list of supported styles.
        
        Returns:
            List of style names
        """
        return []
