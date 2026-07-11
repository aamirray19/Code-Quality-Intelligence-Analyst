import asyncio
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.errors import AppError

GOOGLE_AI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Backoff applied between retries of the same (key, model) after a 429;
# indexed by attempt number, capped at the last entry. Shared by every
# caller that retries LLM_RATE_LIMITED errors (agent_factory, report_builder_service).
RATE_LIMIT_BACKOFF_SECONDS = [2, 5, 10]

AGENT_KEY_ATTR = {
    "supervisor": "google_api_key_supervisor",
    "security": "google_api_key_security",
    "performance": "google_api_key_performance",
    "complexity": "google_api_key_complexity",
    "duplication": "google_api_key_duplication",
    "reliability": "google_api_key_reliability",
    "chatbot": "google_api_key_chatbot",
}


class LLMClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


def _extract_answer_text(data: dict) -> str:
    """Pull the real answer out of a generateContent response.

    When thinking is enabled, `parts` can contain a reasoning-trace part
    marked `"thought": true` ahead of the actual answer part — naively taking
    parts[0] returns the reasoning trace, not the answer. thinkingBudget=0 in
    the request should prevent this, but this filters defensively in case a
    given model variant still emits one anyway.
    """
    parts = data["candidates"][0]["content"]["parts"]
    text_parts = [part["text"] for part in parts if not part.get("thought")]
    if not text_parts:
        raise KeyError("no non-thought parts in response")
    return "".join(text_parts)


class GoogleAIClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: int = 120):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        # Populated by the most recent successful `complete()` call so callers
        # (agent_factory._record_agent_run) can persist token usage without
        # changing the LLMClient Protocol's `complete()` signature. Keys are
        # OpenAI-style names (prompt_tokens/completion_tokens/total_tokens),
        # mapped from Gemini's native usageMetadata field names, so every
        # downstream consumer written against the old OpenRouter client needs
        # no changes.
        self.last_usage: dict | None = None

    async def complete(self, *, system: str, user: str) -> str:
        if not self._api_key:
            raise AppError("LLM_NOT_CONFIGURED", "Google AI API key is not configured.", 500)

        url = GOOGLE_AI_URL.format(model=self._model)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "systemInstruction": {"parts": [{"text": system}]},
            # NOTE: thinkingConfig/thinkingBudget is Gemini-only — Gemma models
            # reject it outright with 400 "Thinking budget is not supported for
            # this model." (confirmed live). Gemma's thinking mode can't be
            # disabled via request config, so _extract_answer_text below is the
            # only defense against a stray "thought": true part in the response.
            "generationConfig": {"maxOutputTokens": 4096},
        }

        try:
            # httpx's per-operation timeout resets on any trickle of bytes
            # (e.g. a long generation's keep-alive), so it doesn't cap total
            # call duration. wait_for enforces a hard wall-clock deadline on
            # top of it.
            async def _post() -> httpx.Response:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    return await client.post(url, params={"key": self._api_key}, json=payload)

            response = await asyncio.wait_for(_post(), timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            # Surface 429 with a distinct error_code so callers (agent_factory's
            # retry/fallback cascade) can back off and escalate model/key instead
            # of treating it like any other request failure.
            if exc.response is not None and exc.response.status_code == 429:
                raise AppError(
                    "LLM_RATE_LIMITED", f"Google AI request failed: {exc}", 502
                ) from exc
            raise AppError("LLM_REQUEST_FAILED", f"Google AI request failed: {exc}", 502) from exc
        except (httpx.HTTPError, ValueError, asyncio.TimeoutError) as exc:
            raise AppError("LLM_REQUEST_FAILED", f"Google AI request failed: {exc}", 502) from exc

        try:
            content = _extract_answer_text(data)
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                "LLM_RESPONSE_MALFORMED", f"Unexpected Google AI response shape: {exc}", 502
            ) from exc

        usage = data.get("usageMetadata") or {}
        self.last_usage = {
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
            "total_tokens": usage.get("totalTokenCount"),
        }
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


def build_llm_client(agent_name: str) -> GoogleAIClient:
    """Construct a GoogleAIClient bound to the dedicated API key for
    `agent_name` (one of: supervisor, security, performance, complexity,
    duplication, reliability, chatbot)."""
    key_attr = AGENT_KEY_ATTR[agent_name]
    api_key = getattr(settings, key_attr) or ""
    return GoogleAIClient(
        api_key=api_key, model=settings.agent_llm_model, timeout_seconds=settings.agent_timeout_seconds
    )
