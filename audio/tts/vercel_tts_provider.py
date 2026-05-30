from audio.playback import play_mp3_async
from audio.tts.base_tts import BaseTTS
from client import vercel_client


class VercelTTSProvider(BaseTTS):
    """TTS proxy through the Vercel backend so no ElevenLabs key ships in app."""

    async def speak(self, text: str) -> None:
        if not text.strip():
            return

        audio_bytes = await vercel_client.get_tts_audio(text)
        await play_mp3_async(audio_bytes)
