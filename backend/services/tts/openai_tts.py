"""OpenAI TTS provider implementation."""

from typing import AsyncIterator

from loguru import logger
from openai import AsyncOpenAI

from backend.services.tts.base import TTSProvider, TTSResult, TTSVoice


class OpenAITTS(TTSProvider):
    """OpenAI TTS provider.
    
    Supports models: tts-1, tts-1-hd
    Supports voices: alloy, echo, fable, onyx, nova, shimmer
    """
    
    VOICES = [
        TTSVoice("alloy", "Alloy", "neutral"),
        TTSVoice("echo", "Echo", "male"),
        TTSVoice("fable", "Fable", "neutral"),
        TTSVoice("onyx", "Onyx", "male"),
        TTSVoice("nova", "Nova", "female"),
        TTSVoice("shimmer", "Shimmer", "female"),
    ]
    
    DEFAULT_MODEL = "tts-1"
    DEFAULT_VOICE = "alloy"
    DEFAULT_RESPONSE_FORMAT = "mp3"
    
    def __init__(self, api_key: str, base_url: str = None):
        """Initialize OpenAI TTS provider.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API (for proxies)
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    async def synthesize(
        self,
        text: str,
        voice: str = None,
        model: str = None,
        speed: float = 1.0,
        style: str = None,
        audio_tags: str = None
    ) -> TTSResult:
        """Synthesize text to speech using OpenAI TTS.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (alloy, echo, fable, onyx, nova, shimmer)
            model: Model ID (tts-1, tts-1-hd)
            speed: Speech speed (0.25-4.0)
            style: Not supported by OpenAI TTS
            audio_tags: Not supported by OpenAI TTS
            
        Returns:
            TTSResult with MP3 audio data
        """
        voice = voice or self.DEFAULT_VOICE
        model = model or self.DEFAULT_MODEL
        
        logger.debug(f"OpenAI TTS: synthesizing with voice={voice}, model={model}, speed={speed}")
        
        response = await self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
            response_format=self.DEFAULT_RESPONSE_FORMAT
        )
        
        audio_data = response.content
        
        return TTSResult(
            audio_data=audio_data,
            format=self.DEFAULT_RESPONSE_FORMAT,
            duration_ms=0
        )
    
    async def synthesize_stream(
        self,
        text: str,
        voice: str = None,
        model: str = None,
        speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        """Stream synthesis using OpenAI TTS.
        
        Args:
            text: Text to synthesize
            voice: Voice ID
            model: Model ID
            speed: Speech speed
            
        Yields:
            Audio data chunks
        """
        voice = voice or self.DEFAULT_VOICE
        model = model or self.DEFAULT_MODEL
        
        response = await self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
            response_format=self.DEFAULT_RESPONSE_FORMAT
        )
        
        async for chunk in response.iter_bytes():
            yield chunk
    
    def get_available_voices(self) -> list[TTSVoice]:
        """Get list of available OpenAI voices.
        
        Returns:
            List of TTSVoice objects
        """
        return self.VOICES.copy()
