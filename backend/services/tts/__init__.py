"""TTS (Text-to-Speech) service module."""

from backend.services.tts.base import TTSProvider, TTSResult, TTSVoice
from backend.services.tts.factory import TTSFactory

__all__ = ["TTSProvider", "TTSResult", "TTSVoice", "TTSFactory"]
