"""MiMo TTS provider implementation with style control support."""

import base64
from typing import AsyncIterator

from loguru import logger
from openai import AsyncOpenAI

from backend.services.tts.base import TTSProvider, TTSResult, TTSVoice


class MiMoTTS(TTSProvider):
    """MiMo TTS provider with style control and audio tags support.
    
    Style control examples:
    - <style>开心</style>明天就是周五了，真开心！
    - <style>东北话</style>哎呀妈呀，这天儿也忒冷了吧！
    - <style>唱歌</style>原谅我这一生不羁放纵爱自由...
    
    Audio tags examples:
    - （紧张，深呼吸）呼……冷静，冷静。
    - （极其疲惫，有气无力）师傅……到地方了叫我一声……
    """
    
    VOICES = [
        TTSVoice("mimo_default", "MiMo-默认", "neutral", "zh"),
        TTSVoice("default_zh", "MiMo-中文女声", "female", "zh"),
        TTSVoice("default_en", "MiMo-英文女声", "female", "en"),
    ]
    
    SUPPORTED_STYLES = [
        {"id": "开心", "name": "开心", "category": "emotion"},
        {"id": "悲伤", "name": "悲伤", "category": "emotion"},
        {"id": "生气", "name": "生气", "category": "emotion"},
        {"id": "悄悄话", "name": "悄悄话", "category": "special"},
        {"id": "夹子音", "name": "夹子音", "category": "special"},
        {"id": "台湾腔", "name": "台湾腔", "category": "dialect"},
        {"id": "东北话", "name": "东北话", "category": "dialect"},
        {"id": "四川话", "name": "四川话", "category": "dialect"},
        {"id": "河南话", "name": "河南话", "category": "dialect"},
        {"id": "粤语", "name": "粤语", "category": "dialect"},
        {"id": "唱歌", "name": "唱歌", "category": "special"},
    ]
    
    DEFAULT_MODEL = "mimo-v2-tts"
    DEFAULT_VOICE = "mimo_default"
    DEFAULT_FORMAT = "wav"
    
    def __init__(self, api_key: str, base_url: str = "https://api.xiaomimimo.com/v1"):
        """Initialize MiMo TTS provider.
        
        Args:
            api_key: MiMo API key
            base_url: MiMo API base URL
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    def supports_style_control(self) -> bool:
        """MiMo TTS supports style control."""
        return True
    
    def supports_audio_tags(self) -> bool:
        """MiMo TTS supports audio tags."""
        return True
    
    def get_supported_styles(self) -> list[str]:
        """Get list of supported styles."""
        return [s["id"] for s in self.SUPPORTED_STYLES]
    
    async def synthesize(
        self,
        text: str,
        voice: str = None,
        model: str = None,
        speed: float = 1.0,
        style: str = None,
        audio_tags: str = None,
        format: str = None
    ) -> TTSResult:
        """Synthesize text to speech using MiMo TTS.
        
        Args:
            text: Text to synthesize
            voice: Voice ID (mimo_default, default_zh, default_en)
            model: Model ID (mimo-v2-tts)
            speed: Speech speed (not used by MiMo)
            style: Style for style control (e.g., "开心", "东北话")
            audio_tags: Fine-grained audio control tags
            format: Audio format (wav, mp3, pcm16)
            
        Returns:
            TTSResult with audio data
        """
        voice = voice or self.DEFAULT_VOICE
        model = model or self.DEFAULT_MODEL
        format = format or self.DEFAULT_FORMAT
        
        processed_text = text
        
        if style:
            processed_text = f"<style>{style}</style>{processed_text}"
        
        if audio_tags:
            processed_text = f"（{audio_tags}）{processed_text}"
        
        logger.debug(f"MiMo TTS: synthesizing with voice={voice}, model={model}, style={style}")
        
        completion = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "assistant", "content": processed_text}
            ],
            audio={
                "format": format,
                "voice": voice
            }
        )
        
        audio_data = base64.b64decode(completion.choices[0].message.audio.data)
        
        return TTSResult(
            audio_data=audio_data,
            format=format,
            duration_ms=0
        )
    
    async def synthesize_stream(
        self,
        text: str,
        voice: str = None,
        model: str = None,
        speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        """Stream synthesis using MiMo TTS (PCM16 format).
        
        Args:
            text: Text to synthesize
            voice: Voice ID
            model: Model ID
            speed: Speech speed (not used)
            
        Yields:
            PCM16 audio data chunks
        """
        voice = voice or self.DEFAULT_VOICE
        model = model or self.DEFAULT_MODEL
        
        completion = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "assistant", "content": text}],
            audio={"format": "pcm16", "voice": voice},
            stream=True
        )
        
        async for chunk in completion:
            if chunk.choices and chunk.choices[0].delta:
                audio = getattr(chunk.choices[0].delta, "audio", None)
                if audio and isinstance(audio, dict) and "data" in audio:
                    yield base64.b64decode(audio["data"])
    
    def get_available_voices(self) -> list[TTSVoice]:
        """Get list of available MiMo voices.
        
        Returns:
            List of TTSVoice objects
        """
        return self.VOICES.copy()
