import asyncio
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.errors import AppError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

AGENT_KEY_ATTR = {
    "supervisor": "openrouter_api_key_supervisor",
    "security": "openrouter_api_key_security",
    "performance": "openrouter_api_key_performance",
    "complexity": "openrouter_api_key_complexity",
    "duplication": "openrouter_api_key_duplication",
    "reliability": "openrouter_api_key_reliability",
    "chatbot": "openrouter_api_key_chatbot",
}


class LLMClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class OpenRouterClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: int = 120):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        # Populated by the most recent successful `complete()` call so callers
        # (agent_factory._record_agent_run) can persist token usage without
        # changing the LLMClient Protocol's `complete()` signature.
        self.last_usage: dict | None = None

    async def complete(self, *, system: str, user: str) -> str:
        if not self._api_key:
            raise AppError("LLM_NOT_CONFIGURED", "OpenRouter API key is not configured.", 500)

        # NOTE: build a real Bearer header — interpolate the configured
        # API key into the Authorization header value (do not hardcode or
        # mask this string).
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 4096,
        }

        try:
            # httpx's per-operation timeout resets on any trickle of bytes
            # (e.g. OpenRouter's keep-alive during a long generation), so it
            # doesn't cap total call duration. wait_for enforces a hard
            # wall-clock deadline on top of it.
            async def _post() -> httpx.Response:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    return await client.post(OPENROUTER_URL, headers=headers, json=payload)

            response = await asyncio.wait_for(_post(), timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError, asyncio.TimeoutError) as exc:
            raise AppError("LLM_REQUEST_FAILED", f"OpenRouter request failed: {exc}", 502) from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                "LLM_RESPONSE_MALFORMED", f"Unexpected OpenRouter response shape: {exc}", 502
            ) from exc

        self.last_usage = data.get("usage")
        return content


class FakeLLMClient:
    """Test double implementing LLMClient; returns a canned response and
    records every call made to it for assertions in node/graph tests."""

    def __init__(self, response: str):
        self._response = response
        self.calls: list[dict] = []
        self.last_usage: dict | None = None

    async def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self._response


def build_llm_client(agent_name: str) -> OpenRouterClient:
    """Construct an OpenRouterClient bound to the dedicated API key for
    `agent_name` (one of: supervisor, security, performance, complexity,
    duplication, reliability). No cross-key fallback exists by design."""
    key_attr = AGENT_KEY_ATTR[agent_name]
    api_key = getattr(settings, key_attr) or ""
    return OpenRouterClient(
        api_key=api_key, model=settings.agent_llm_model, timeout_seconds=settings.agent_timeout_seconds
    )
