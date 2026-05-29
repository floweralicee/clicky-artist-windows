import base64
from typing import AsyncIterator, List

import httpx

from ai.base_provider import BaseLLMProvider, Message
from ai.ollama_models_registry import is_vision_capable
from config import cfg

OLLAMA_SETUP_MESSAGE = (
    "clicky needs ollama to run.\n"
    "visit floweralice.me/clicky for setup instructions."
)


class OllamaProvider(BaseLLMProvider):
    """
    Streams responses from a local Ollama instance.

    Auto-picks the right model per call:
        • Screenshots present → cfg.get_ollama_model("vision")
        • No screenshots      → cfg.get_ollama_model("text")

    A caller may still pass an explicit `model=` to override that choice
    (e.g. the panel's manual model dropdown).
    """

    def __init__(self):
        self._base = cfg.ollama_host.rstrip("/")
        self._model = cfg.get_ollama_model("vision")

    def _pick_model(self, has_screenshots: bool) -> str:
        return cfg.get_ollama_model("vision" if has_screenshots else "text")

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        # Resolution order:
        #   1. explicit `model=` arg (panel override)
        #   2. cfg vision/text slot based on attachment kind
        if model:
            chosen = model
        else:
            chosen = self._pick_model(bool(screenshots_b64))

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Ollama passes images as base64 strings inside the message
        user_msg: dict = {"role": "user", "content": user_text}
        if screenshots_b64:
            user_msg["images"] = screenshots_b64
        messages.append(user_msg)

        payload = {
            "model": chosen,
            "messages": messages,
            "stream": True,
            "options": {"num_predict": 1024},
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self._base}/api/chat",
                    json=payload,
                ) as response:
                    if response.status_code == 404:
                        raise RuntimeError(
                            f"Ollama doesn't have '{chosen}' installed. "
                            f"Run `ollama pull {chosen}` or pick another model "
                            f"from Tray → Ollama."
                        )
                    response.raise_for_status()
                    import json
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except (httpx.ConnectError, httpx.ConnectTimeout, OSError):
            raise RuntimeError(OLLAMA_SETUP_MESSAGE) from None

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self._base}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """Return all installed model names (flat list)."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self._base}/api/tags")
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    async def list_models_classified(self) -> dict[str, list[str]]:
        """Installed models split into {'vision': [...], 'text': [...]}.

        Heuristic-based — see ollama_models_registry.is_vision_capable().
        """
        names = await self.list_models()
        out: dict[str, list[str]] = {"vision": [], "text": []}
        for n in names:
            if is_vision_capable(n):
                out["vision"].append(n)
            else:
                out["text"].append(n)
        out["vision"].sort()
        out["text"].sort()
        return out
