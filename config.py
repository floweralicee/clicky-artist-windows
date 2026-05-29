import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load env files in priority order. .env.local overrides .env.
_HERE = Path(__file__).parent
for _name in (".env", ".env.local"):
    _p = _HERE / _name
    if _p.exists():
        load_dotenv(_p, override=True)

# Clicky for Animators — hardcoded defaults (Ollama + local STT/TTS only)
CLICKY_ACTIVE_LLM = "ollama"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_VISION_MODEL = "qwen2-vl:7b"
OLLAMA_TEXT_MODEL = "qwen2.5-coder:7b"
CLICKY_STT = "faster_whisper"
WHISPER_MODEL = "base"


@dataclass
class Config:
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", OLLAMA_HOST)
    )
    ollama_vision_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_VISION_MODEL", OLLAMA_VISION_MODEL)
        or OLLAMA_VISION_MODEL
    )
    ollama_text_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_TEXT_MODEL", OLLAMA_TEXT_MODEL)
        or OLLAMA_TEXT_MODEL
    )
    whisper_model: str = field(
        default_factory=lambda: os.getenv("WHISPER_MODEL", WHISPER_MODEL)
    )

    # Optional web search upgrade — not an LLM/STT/TTS provider
    tavily_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY") or None
    )

    hotkey: str = field(
        default_factory=lambda: os.getenv("CLICKY_HOTKEY", "ctrl+alt+space")
    )

    def llm_provider(self) -> str:
        """Always Ollama — no cloud provider chain."""
        return CLICKY_ACTIVE_LLM

    def available_llm_providers(self) -> list[str]:
        return [CLICKY_ACTIVE_LLM]

    def set_active_llm(self, name: str) -> None:
        # No-op — Ollama is the only LLM in this fork
        pass

    def stt_provider(self) -> str:
        """Always Faster-Whisper — local, no API key."""
        return CLICKY_STT

    def tts_provider(self) -> str:
        """Always Edge TTS — free, no API key."""
        return "edge_tts"

    def search_provider(self) -> str:
        if self.tavily_api_key:
            return "tavily"
        return "duckduckgo"

    def describe(self) -> dict:
        """Human-readable summary of active providers for the setup panel."""
        return {
            "llm": self.llm_provider(),
            "stt": self.stt_provider(),
            "tts": self.tts_provider(),
            "search": self.search_provider(),
            "ollama_vision_model": self.get_ollama_model("vision"),
            "ollama_text_model": self.get_ollama_model("text"),
        }

    def get_ollama_model(self, kind: str = "vision") -> str:
        """Return the active model for the given kind ("vision" | "text")."""
        env_key = (
            "CLICKY_OLLAMA_VISION_MODEL"
            if kind == "vision"
            else "CLICKY_OLLAMA_TEXT_MODEL"
        )
        runtime = os.environ.get(env_key, "").strip()
        if runtime:
            return runtime
        return (
            self.ollama_vision_model if kind == "vision" else self.ollama_text_model
        )

    def set_ollama_model(self, kind: str, name: str) -> None:
        """Runtime switch for vision/text Ollama model. Persists for the session."""
        if kind not in ("vision", "text"):
            return
        env_key = (
            "CLICKY_OLLAMA_VISION_MODEL"
            if kind == "vision"
            else "CLICKY_OLLAMA_TEXT_MODEL"
        )
        os.environ[env_key] = (name or "").strip()
        if kind == "vision":
            self.ollama_vision_model = name
        else:
            self.ollama_text_model = name


# Singleton
cfg = Config()
