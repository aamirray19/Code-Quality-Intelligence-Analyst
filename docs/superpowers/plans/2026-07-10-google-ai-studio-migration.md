# Google AI Studio Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace OpenRouter as the LLM provider for all 5 specialist agents, the supervisor, and the chatbot/report-generation calls with Google AI Studio (Gemini API), while keeping every consumer-facing interface, the retry/backoff/candidate-cascade flow, and the concurrency semaphore byte-for-byte identical.

**Architecture:** `openrouter_client.py` is replaced by a new `google_ai_client.py` implementing the exact same `GoogleAIClient` interface (`__init__(api_key, model, timeout_seconds)`, `async complete(*, system, user) -> str`, `self.last_usage` dict) and the exact same `build_llm_client(agent_name)` / `AGENT_KEY_ATTR` / `RATE_LIMIT_BACKOFF_SECONDS` module surface that `agent_factory.py`, `report_builder_service.py`, `build_analysis_plan.py`, and `chatbot_service.py` already depend on. Every consumer is migrated one at a time, verified via its existing test suite, before the old file is deleted last.

**Tech Stack:** Python 3.11, `httpx` (async, already a dependency — no new package needed), `pytest` + `pytest-asyncio` + `respx` for tests, Gemini REST API (`generativelanguage.googleapis.com`).

## Global Constraints

- No behavior change to the retry/backoff/candidate-cascade logic in `agent_factory.py` (`_llm_candidates`, `RATE_LIMIT_BACKOFF_SECONDS`, backoff-on-429) or the `AGENT_LLM_CONCURRENCY_LIMIT` semaphore — these are provider-agnostic and untouched by this migration.
- `GoogleAIClient.complete()` must keep the exact same signature, return type, and `self.last_usage` dict *key names* (`prompt_tokens`, `completion_tokens`, `total_tokens`) as `OpenRouterClient` did, even though Gemini's native usage field names differ (`promptTokenCount` etc.) — this is the adapter boundary that keeps every downstream consumer's code unchanged.
- Error codes stay identical: `LLM_NOT_CONFIGURED`, `LLM_REQUEST_FAILED`, `LLM_RATE_LIMITED` (on HTTP 429), `LLM_RESPONSE_MALFORMED`.
- Primary model: `gemini-2.5-flash`. Fallback model: `gemini-2.5-flash-lite` (confirmed free-tier as of 2026-07-10; Flash-Lite has a materially higher daily quota, mirroring the primary-tighter/fallback-looser pattern already in use).
- Settings/env var naming: `openrouter_api_key_*` → `google_api_key_*` (same suffixes), `OPENROUTER_API_KEY_*` → `GOOGLE_API_KEY_*`, `agent_llm_provider` value `"openrouter"` → `"google"`.
- No git commit steps in this plan (standing project preference — see `handoff.md` 2026-07-06/07-07 entries).

---

### Task 1: Build `google_ai_client.py` in isolation, fully tested

**Files:**
- Create: `backend/app/services/google_ai_client.py`
- Create: `backend/tests/test_google_ai_client.py`

**Interfaces:**
- Produces: `GoogleAIClient(api_key: str, model: str, timeout_seconds: int = 120)` with `async def complete(self, *, system: str, user: str) -> str` and `self.last_usage: dict | None`; `FakeLLMClient` (unchanged copy); `AGENT_KEY_ATTR: dict[str, str]` mapping agent name → settings attribute name; `RATE_LIMIT_BACKOFF_SECONDS: list[int]`; `build_llm_client(agent_name: str) -> GoogleAIClient`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_google_ai_client.py
import httpx
import pytest
import respx

from app.core.errors import AppError
from app.services.google_ai_client import FakeLLMClient, GoogleAIClient, build_llm_client

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


@pytest.mark.asyncio
@respx.mock
async def test_complete_returns_message_content():
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [{"content": {"role": "model", "parts": [{"text": "[]"}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 2, "totalTokenCount": 12},
            },
        )
    )
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    result = await client.complete(system="sys", user="user")
    assert result == "[]"


@pytest.mark.asyncio
@respx.mock
async def test_complete_maps_usage_metadata_to_openai_style_keys():
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50, "totalTokenCount": 150},
            },
        )
    )
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    await client.complete(system="sys", user="user")
    assert client.last_usage == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


@pytest.mark.asyncio
async def test_complete_raises_when_key_missing():
    client = GoogleAIClient(api_key="", model="gemini-2.5-flash")
    with pytest.raises(AppError) as exc_info:
        await client.complete(system="sys", user="user")
    assert exc_info.value.error_code == "LLM_NOT_CONFIGURED"


@pytest.mark.asyncio
@respx.mock
async def test_complete_raises_app_error_on_http_failure():
    respx.post(GEMINI_URL).mock(return_value=httpx.Response(500, json={"error": {"message": "boom"}}))
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    with pytest.raises(AppError) as exc_info:
        await client.complete(system="sys", user="user")
    assert exc_info.value.error_code == "LLM_REQUEST_FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_complete_raises_llm_rate_limited_on_429():
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(429, json={"error": {"message": "RESOURCE_EXHAUSTED"}})
    )
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    with pytest.raises(AppError) as exc_info:
        await client.complete(system="sys", user="user")
    assert exc_info.value.error_code == "LLM_RATE_LIMITED"


@pytest.mark.asyncio
@respx.mock
async def test_complete_raises_response_malformed_on_missing_candidates():
    respx.post(GEMINI_URL).mock(return_value=httpx.Response(200, json={"candidates": []}))
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    with pytest.raises(AppError) as exc_info:
        await client.complete(system="sys", user="user")
    assert exc_info.value.error_code == "LLM_RESPONSE_MALFORMED"


@pytest.mark.asyncio
async def test_fake_llm_client_records_calls():
    fake = FakeLLMClient(response="canned")
    result = await fake.complete(system="sys", user="user")
    assert result == "canned"
    assert fake.calls == [{"system": "sys", "user": "user"}]


def test_build_llm_client_uses_supervisor_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_api_key_supervisor", "sup-key")
    client = build_llm_client("supervisor")
    assert client._api_key == "sup-key"


def test_build_llm_client_uses_chatbot_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_api_key_chatbot", "chatbot-key")
    client = build_llm_client("chatbot")
    assert client._api_key == "chatbot-key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_google_ai_client.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'app.services.google_ai_client'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/google_ai_client.py
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
            content = data["candidates"][0]["content"]["parts"][0]["text"]
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
```

- [ ] **Step 4: Add the new settings this file depends on**

`GoogleAIClient`/`build_llm_client` reference `settings.google_api_key_*` and `settings.agent_llm_model`. Add the new settings now so Step 5's tests can pass — full config rename happens in Task 2, but the client needs these specific attributes to exist first. In `backend/app/core/config.py`, add (do not remove the `openrouter_*` ones yet — Task 2 does that once every consumer is migrated):

```python
    # Google AI Studio (Gemini) — migrated from OpenRouter, see decisions.md 2026-07-10
    google_api_key_supervisor: str | None = None
    google_api_key_security: str | None = None
    google_api_key_performance: str | None = None
    google_api_key_complexity: str | None = None
    google_api_key_duplication: str | None = None
    google_api_key_reliability: str | None = None
    google_api_key_security_fallback: str | None = None
    google_api_key_performance_fallback: str | None = None
    google_api_key_complexity_fallback: str | None = None
    google_api_key_duplication_fallback: str | None = None
    google_api_key_reliability_fallback: str | None = None
    google_api_key_chatbot: str | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_google_ai_client.py -v`
Expected: 9 passed

---

### Task 2: Rename `agent_llm_provider`/model settings, finish config + `.env.example`

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Consumes: nothing new.
- Produces: `settings.agent_llm_provider == "google"`, `settings.agent_llm_model == "gemini-2.5-flash"`, `settings.agent_llm_model_fallback == "gemini-2.5-flash-lite"` — relied on by Task 1's already-passing `google_ai_client.py` and every later task.

- [ ] **Step 1: Update `agent_llm_provider`/`agent_llm_model`/`agent_llm_model_fallback` in `config.py`**

Find this block (added in the 2026-07-10 model-fallback work):

```python
    # Phase 3: OpenRouter LLM client
    agent_llm_provider: str = "openrouter"
    agent_llm_model: str = "google/gemma-4-31b-it:free"
    # Escalation model tried on the same key once agent_llm_model keeps 429ing.
    agent_llm_model_fallback: str = "google/gemma-4-26b-a4b-it:free"
```

Replace with:

```python
    # Phase 3: Google AI Studio (Gemini) LLM client — migrated from OpenRouter,
    # see decisions.md 2026-07-10.
    agent_llm_provider: str = "google"
    agent_llm_model: str = "gemini-2.5-flash"
    # Escalation model tried on the same key once agent_llm_model keeps 429ing.
    agent_llm_model_fallback: str = "gemini-2.5-flash-lite"
```

- [ ] **Step 2: Remove the old `openrouter_api_key_*` settings, keep the `google_api_key_*` ones from Task 1**

Find and delete this block (the `google_api_key_*` block from Task 1 Step 4 stays as-is, right below where this was):

```python
    openrouter_api_key_supervisor: str | None = None
    openrouter_api_key_security: str | None = None
    openrouter_api_key_performance: str | None = None
    openrouter_api_key_complexity: str | None = None
    openrouter_api_key_duplication: str | None = None
    openrouter_api_key_reliability: str | None = None
    # Optional second key per specialist agent. If set, tried (with both models
    # above) after the primary key exhausts its own rate-limit retries.
    openrouter_api_key_security_fallback: str | None = None
    openrouter_api_key_performance_fallback: str | None = None
    openrouter_api_key_complexity_fallback: str | None = None
    openrouter_api_key_duplication_fallback: str | None = None
    openrouter_api_key_reliability_fallback: str | None = None
```

- [ ] **Step 3: Remove `openrouter_api_key_chatbot`, keep `google_api_key_chatbot`**

Find (in the Phase 4 section):

```python
    # Phase 4: Report generation & RAG chatbot
    openrouter_api_key_chatbot: str | None = None
```

Replace with:

```python
    # Phase 4: Report generation & RAG chatbot
    # google_api_key_chatbot is defined above in the Phase 3 Google AI block.
```

- [ ] **Step 4: Update `.env.example` to match**

Replace the `# Phase 3: OpenRouter LLM client` block:

```env
# Phase 3: OpenRouter LLM client
AGENT_LLM_PROVIDER=openrouter
AGENT_LLM_MODEL=google/gemma-4-31b-it:free
# Escalation model tried on the same key once AGENT_LLM_MODEL keeps 429ing.
AGENT_LLM_MODEL_FALLBACK=google/gemma-4-26b-a4b-it:free
OPENROUTER_API_KEY_SUPERVISOR=
OPENROUTER_API_KEY_SECURITY=
OPENROUTER_API_KEY_PERFORMANCE=
OPENROUTER_API_KEY_COMPLEXITY=
OPENROUTER_API_KEY_DUPLICATION=
OPENROUTER_API_KEY_RELIABILITY=
# Optional second key per specialist agent. If set, tried (with both models
# above) after the primary key exhausts its own rate-limit retries.
OPENROUTER_API_KEY_SECURITY_FALLBACK=
OPENROUTER_API_KEY_PERFORMANCE_FALLBACK=
OPENROUTER_API_KEY_COMPLEXITY_FALLBACK=
OPENROUTER_API_KEY_DUPLICATION_FALLBACK=
OPENROUTER_API_KEY_RELIABILITY_FALLBACK=
```

with:

```env
# Phase 3: Google AI Studio (Gemini) LLM client — migrated from OpenRouter,
# see decisions.md 2026-07-10. NOTE: free-tier rate limits apply per Google
# Cloud project, not per API key — separate GOOGLE_API_KEY_* values only give
# real fallback headroom if each key comes from a different GCP project.
AGENT_LLM_PROVIDER=google
AGENT_LLM_MODEL=gemini-2.5-flash
# Escalation model tried on the same key once AGENT_LLM_MODEL keeps 429ing.
AGENT_LLM_MODEL_FALLBACK=gemini-2.5-flash-lite
GOOGLE_API_KEY_SUPERVISOR=
GOOGLE_API_KEY_SECURITY=
GOOGLE_API_KEY_PERFORMANCE=
GOOGLE_API_KEY_COMPLEXITY=
GOOGLE_API_KEY_DUPLICATION=
GOOGLE_API_KEY_RELIABILITY=
# Optional second key per specialist agent. If set, tried (with both models
# above) after the primary key exhausts its own rate-limit retries.
GOOGLE_API_KEY_SECURITY_FALLBACK=
GOOGLE_API_KEY_PERFORMANCE_FALLBACK=
GOOGLE_API_KEY_COMPLEXITY_FALLBACK=
GOOGLE_API_KEY_DUPLICATION_FALLBACK=
GOOGLE_API_KEY_RELIABILITY_FALLBACK=
```

And replace `OPENROUTER_API_KEY_CHATBOT=` under `# Phase 4: Report generation & RAG chatbot` with `GOOGLE_API_KEY_CHATBOT=`.

- [ ] **Step 5: Run the full config + google_ai_client tests to verify no regressions yet**

Run: `cd backend && uv run pytest tests/test_google_ai_client.py -v`
Expected: 9 passed (unchanged from Task 1 — this task only touched settings names the client already relies on)

Note: `tests/test_config.py` and `tests/test_openrouter_client.py` will FAIL after this step — that's expected and fixed in Tasks 3-7 below. Do not run the full suite yet.

---

### Task 3: Migrate `agent_factory.py` to `GoogleAIClient`

**Files:**
- Modify: `backend/app/workflows/analysis/agents/agent_factory.py`
- Modify: `backend/tests/test_agents.py`
- Modify: `backend/tests/test_analysis_graph.py`

**Interfaces:**
- Consumes: `GoogleAIClient`, `AGENT_KEY_ATTR`, `RATE_LIMIT_BACKOFF_SECONDS` from `app.services.google_ai_client` (Task 1).
- Produces: no change to `run_agent`'s public behavior — `_llm_candidates()` now reads `google_api_key_*` settings instead of `openrouter_api_key_*`, everything else identical.

- [ ] **Step 1: Update the import in `agent_factory.py`**

Find:

```python
from app.services.openrouter_client import (
    AGENT_KEY_ATTR,
    RATE_LIMIT_BACKOFF_SECONDS,
    OpenRouterClient,
)
```

Replace with:

```python
from app.services.google_ai_client import (
    AGENT_KEY_ATTR,
    RATE_LIMIT_BACKOFF_SECONDS,
    GoogleAIClient,
)
```

- [ ] **Step 2: Update `_llm_candidates`'s fallback-key attribute names**

Find:

```python
FALLBACK_KEY_ATTR = {
    "security": "openrouter_api_key_security_fallback",
    "performance": "openrouter_api_key_performance_fallback",
    "complexity": "openrouter_api_key_complexity_fallback",
    "duplication": "openrouter_api_key_duplication_fallback",
    "reliability": "openrouter_api_key_reliability_fallback",
}
```

Replace with:

```python
FALLBACK_KEY_ATTR = {
    "security": "google_api_key_security_fallback",
    "performance": "google_api_key_performance_fallback",
    "complexity": "google_api_key_complexity_fallback",
    "duplication": "google_api_key_duplication_fallback",
    "reliability": "google_api_key_reliability_fallback",
}
```

- [ ] **Step 3: Update the two type annotations and the one construction site**

Find (in `run_agent`'s signature area): `client: OpenRouterClient | None = None` → replace with `client: GoogleAIClient | None = None`.

Find (inside the candidate loop):

```python
            for key, model in _llm_candidates(agent_name):
                client = OpenRouterClient(
                    api_key=key, model=model, timeout_seconds=settings.agent_timeout_seconds
                )
```

Replace with:

```python
            for key, model in _llm_candidates(agent_name):
                client = GoogleAIClient(
                    api_key=key, model=model, timeout_seconds=settings.agent_timeout_seconds
                )
```

- [ ] **Step 4: Update `test_agents.py`'s 3 patch targets**

In `backend/tests/test_agents.py`, all 3 occurrences of:

```python
    with patch(f"{MODULE}.OpenRouterClient", return_value=fake_llm), patch(
```

Replace with:

```python
    with patch(f"{MODULE}.GoogleAIClient", return_value=fake_llm), patch(
```

- [ ] **Step 5: Update `test_analysis_graph.py`'s 1 patch target**

In `backend/tests/test_analysis_graph.py`, find:

```python
        patch(f"{MODULE_FACTORY}.OpenRouterClient", return_value=fake_llm),
```

Replace with:

```python
        patch(f"{MODULE_FACTORY}.GoogleAIClient", return_value=fake_llm),
```

- [ ] **Step 6: Run the affected tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_agents.py tests/test_analysis_graph.py tests/test_google_ai_client.py -v`
Expected: all pass, 0 failed

---

### Task 4: Migrate `report_builder_service.py` to `GoogleAIClient`

**Files:**
- Modify: `backend/app/services/report_builder_service.py`
- Modify: `backend/tests/test_report_builder_service.py`

**Interfaces:**
- Consumes: `AGENT_KEY_ATTR`, `RATE_LIMIT_BACKOFF_SECONDS`, `GoogleAIClient` from `app.services.google_ai_client`.
- Produces: no change to `build_report_markdown`'s public signature or behavior.

- [ ] **Step 1: Update the import**

Find:

```python
from app.services.openrouter_client import (
    AGENT_KEY_ATTR,
    RATE_LIMIT_BACKOFF_SECONDS,
    OpenRouterClient,
)
```

Replace with:

```python
from app.services.google_ai_client import (
    AGENT_KEY_ATTR,
    RATE_LIMIT_BACKOFF_SECONDS,
    GoogleAIClient,
)
```

- [ ] **Step 2: Update the construction site**

Find:

```python
    for model in models:
        client = OpenRouterClient(
            api_key=api_key, model=model, timeout_seconds=settings.agent_timeout_seconds
        )
```

Replace with:

```python
    for model in models:
        client = GoogleAIClient(
            api_key=api_key, model=model, timeout_seconds=settings.agent_timeout_seconds
        )
```

- [ ] **Step 3: Rewrite `test_report_builder_service.py`'s 3 respx-based tests for the Gemini shape**

This file mocks the real HTTP call (not `build_llm_client`), so the URL and response JSON shape both need updating, and the settings attr it monkeypatches needs renaming. In `backend/tests/test_report_builder_service.py`, all 3 occurrences of:

```python
    monkeypatch.setattr(settings, "openrouter_api_key_chatbot", "test-chatbot-key")
```

Replace with:

```python
    monkeypatch.setattr(settings, "google_api_key_chatbot", "test-chatbot-key")
```

All 3 occurrences of:

```python
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": mock_markdown}}]}
        )
    )
```

Replace with:

```python
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"candidates": [{"content": {"role": "model", "parts": [{"text": mock_markdown}]}}]},
        )
    )
```

The assertions further down each test (`request_body = json.loads(request.content)`, `messages = request_body["messages"]`, `all_content = " ".join(msg["content"] for msg in messages)`) read the OpenAI-style `messages` array, which no longer exists in the Gemini request body. In all 3 tests, replace:

```python
    messages = request_body["messages"]
    all_content = " ".join(msg["content"] for msg in messages)
```

with:

```python
    all_content = request_body["systemInstruction"]["parts"][0]["text"] + " " + " ".join(
        p["text"] for c in request_body["contents"] for p in c["parts"]
    )
```

- [ ] **Step 4: Run the affected tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_report_builder_service.py -v`
Expected: 3 passed

---

### Task 5: Migrate `build_analysis_plan.py`'s import (supervisor)

**Files:**
- Modify: `backend/app/workflows/analysis/nodes/build_analysis_plan.py`

**Interfaces:**
- Consumes: `build_llm_client` from `app.services.google_ai_client`.
- Produces: no change — `test_build_analysis_plan.py` patches `build_llm_client` at this module's own namespace (`app.workflows.analysis.nodes.build_analysis_plan.build_llm_client`), so it needs no changes regardless of which underlying client `build_llm_client` returns.

- [ ] **Step 1: Update the import**

Find:

```python
from app.services.openrouter_client import build_llm_client
```

Replace with:

```python
from app.services.google_ai_client import build_llm_client
```

- [ ] **Step 2: Run the existing test to confirm it still passes unmodified**

Run: `cd backend && uv run pytest tests/test_build_analysis_plan.py -v`
Expected: all pass, 0 failed (proves the patch-at-point-of-use pattern insulated this test from the provider swap)

---

### Task 6: Migrate `chatbot_service.py` to `GoogleAIClient`

**Files:**
- Modify: `backend/app/services/chatbot_service.py`
- Modify: `backend/tests/test_chatbot_service.py`

**Interfaces:**
- Consumes: `build_llm_client` from `app.services.google_ai_client`.
- Produces: no change to `classify_question`/`answer_question`'s public signatures.

- [ ] **Step 1: Update the import in `chatbot_service.py`**

Find:

```python
from app.services.openrouter_client import build_llm_client
```

Replace with:

```python
from app.services.google_ai_client import build_llm_client
```

- [ ] **Step 2: Update the 3 tests that directly construct the client**

In `backend/tests/test_chatbot_service.py`, all 3 occurrences of:

```python
    # Mock OpenRouter API to return "..."
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "..."}}]}
        )
    )

    with patch("app.services.chatbot_service.build_llm_client") as mock_build:
        from app.services.openrouter_client import OpenRouterClient

        mock_client = OpenRouterClient(api_key="test-key", model="test-model")
        mock_build.return_value = mock_client
```

(where `"..."` is each test's own return value — `file_specific`, `general`, `something_unexpected`) — replace the respx URL/shape and the import/construction with:

```python
    # Mock Google AI API to return "..."
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    ).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "..."}]}}]}
        )
    )

    with patch("app.services.chatbot_service.build_llm_client") as mock_build:
        from app.services.google_ai_client import GoogleAIClient

        mock_client = GoogleAIClient(api_key="test-key", model="test-model")
        mock_build.return_value = mock_client
```

keeping each test's own `"..."` content value (`file_specific`, `general`, `something_unexpected`) unchanged in both the respx mock and the final assertion.

- [ ] **Step 3: Run the affected tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_chatbot_service.py -v`
Expected: all pass, 0 failed

---

### Task 7: Fix `test_config.py`'s env var reference

**Files:**
- Modify: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: `settings.google_api_key_chatbot` (Task 1/2).
- Produces: nothing new.

- [ ] **Step 1: Update the env var name and assertion**

Find:

```python
    monkeypatch.setenv("OPENROUTER_API_KEY_CHATBOT", "chatbot-key-123")
```

Replace with:

```python
    monkeypatch.setenv("GOOGLE_API_KEY_CHATBOT", "chatbot-key-123")
```

Find:

```python
    assert settings.openrouter_api_key_chatbot == "chatbot-key-123"
```

Replace with:

```python
    assert settings.google_api_key_chatbot == "chatbot-key-123"
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: 2 passed

---

### Task 8: Delete the old OpenRouter files, full-suite verification, docs/decisions

**Files:**
- Delete: `backend/app/services/openrouter_client.py`
- Delete: `backend/tests/test_openrouter_client.py`
- Modify: `docs/phase3.md` (§19 env var block)
- Modify: `decisions.md`

**Interfaces:**
- Consumes: nothing (cleanup task).
- Produces: nothing (cleanup task).

- [ ] **Step 1: Confirm nothing still imports the old module**

Run: `cd backend && grep -rn "openrouter" app/ tests/ --include="*.py" -i`
Expected: no output (every reference was migrated in Tasks 2-7)

- [ ] **Step 2: Delete the old files**

Delete `backend/app/services/openrouter_client.py` and `backend/tests/test_openrouter_client.py` (fully superseded by `google_ai_client.py`/`test_google_ai_client.py` from Task 1).

- [ ] **Step 3: Run the full backend test suite**

Run: `cd backend && uv run pytest -q`
Expected: same pass count as the pre-migration baseline (223 passed per the 2026-07-10 handoff entry), 0 new failures, 0 references to `openrouter` remaining anywhere in a failure message

- [ ] **Step 4: Update `docs/phase3.md` §19**

Find the env var block (corrected earlier today to OpenRouter — see the 2026-07-10 handoff entry):

```env
# Agent LLM
# Superseded (see decisions.md 2026-07-06 + 2026-07-10 entries): the agent/
# supervisor LLM provider is OpenRouter, not DeepSeek directly, and the model
# is a free-tier Gemma model with a fallback, not deepseek-reasoner.
AGENT_LLM_PROVIDER=openrouter
AGENT_LLM_MODEL=google/gemma-4-31b-it:free
AGENT_LLM_MODEL_FALLBACK=google/gemma-4-26b-a4b-it:free
OPENROUTER_API_KEY_SUPERVISOR=
OPENROUTER_API_KEY_SECURITY=
OPENROUTER_API_KEY_PERFORMANCE=
OPENROUTER_API_KEY_COMPLEXITY=
OPENROUTER_API_KEY_DUPLICATION=
OPENROUTER_API_KEY_RELIABILITY=
# Optional second key per specialist agent (security/performance/complexity/
# duplication/reliability only), tried after the primary key exhausts its
# own rate-limit retries on both models above.
OPENROUTER_API_KEY_SECURITY_FALLBACK=
OPENROUTER_API_KEY_PERFORMANCE_FALLBACK=
OPENROUTER_API_KEY_COMPLEXITY_FALLBACK=
OPENROUTER_API_KEY_DUPLICATION_FALLBACK=
OPENROUTER_API_KEY_RELIABILITY_FALLBACK=
```

Replace with:

```env
# Agent LLM
# Superseded again (see decisions.md 2026-07-10 "Google AI Studio migration"
# entry): the agent/supervisor/chatbot LLM provider is Google AI Studio
# (Gemini), not OpenRouter. Free-tier rate limits apply per Google Cloud
# project, not per API key — separate GOOGLE_API_KEY_* values only give real
# fallback headroom if each key comes from a different GCP project.
AGENT_LLM_PROVIDER=google
AGENT_LLM_MODEL=gemini-2.5-flash
AGENT_LLM_MODEL_FALLBACK=gemini-2.5-flash-lite
GOOGLE_API_KEY_SUPERVISOR=
GOOGLE_API_KEY_SECURITY=
GOOGLE_API_KEY_PERFORMANCE=
GOOGLE_API_KEY_COMPLEXITY=
GOOGLE_API_KEY_DUPLICATION=
GOOGLE_API_KEY_RELIABILITY=
# Optional second key per specialist agent (security/performance/complexity/
# duplication/reliability only), tried after the primary key exhausts its
# own rate-limit retries on both models above.
GOOGLE_API_KEY_SECURITY_FALLBACK=
GOOGLE_API_KEY_PERFORMANCE_FALLBACK=
GOOGLE_API_KEY_COMPLEXITY_FALLBACK=
GOOGLE_API_KEY_DUPLICATION_FALLBACK=
GOOGLE_API_KEY_RELIABILITY_FALLBACK=
```

- [ ] **Step 5: Add a `decisions.md` entry**

Append (after the last existing entry):

```markdown
## 2026-07-10: LLM provider switched from OpenRouter to Google AI Studio (Gemini)

- Decision: Replaced OpenRouter with Google AI Studio (Gemini API) as the LLM provider for all 5 specialist agents, the supervisor, and the chatbot/report-generation calls. `openrouter_client.py` was replaced by `google_ai_client.py` implementing an identical `GoogleAIClient`/`build_llm_client`/`AGENT_KEY_ATTR`/`RATE_LIMIT_BACKOFF_SECONDS` surface, so the retry/backoff/candidate-cascade flow and the `AGENT_LLM_CONCURRENCY_LIMIT` semaphore (both added in the 2026-07-10 fallback-cascade and concurrency-fix decisions above) are completely unchanged. Primary model `gemini-2.5-flash`, fallback `gemini-2.5-flash-lite`. `GoogleAIClient.last_usage` maps Gemini's native `usageMetadata` field names to the same OpenAI-style keys (`prompt_tokens`/`completion_tokens`/`total_tokens`) the old client used, so `agent_runs`'s existing columns keep populating with zero downstream changes.
- Reason: User-requested provider switch. Kept the whole flow (cascade, semaphore, error codes, retry/backoff) explicitly unchanged per instruction — this is a provider-adapter swap, not a redesign.
- Alternatives rejected: Keeping the `OpenRouterClient` name and just repointing its internals at Gemini's API — rejected as more confusing long-term than a clean rename, since every call site needed touching regardless of whether the class was renamed.
- Consequences: Google AI Studio's free tier applies rate limits **per Google Cloud project, not per API key** — unlike OpenRouter, provisioning multiple `GOOGLE_API_KEY_*_FALLBACK` values under the same GCP project will NOT provide real fallback headroom; each fallback key needs to come from a separate GCP project to actually isolate quota. This is a meaningful setup difference from the OpenRouter fallback-key architecture and has not yet been verified live.
- Revisit when: Live-tested against real Google AI Studio keys (not yet done as of this decision); or if the per-project quota-sharing behavior proves too limiting even with separate projects.
```

- [ ] **Step 6: Run the full backend test suite one final time**

Run: `cd backend && uv run pytest -q`
Expected: same pass count as Step 3, confirming the docs/decisions edits (markdown-only) introduced no regressions

---

## Self-Review

**Spec coverage:** Every file identified in the "what all needs to change" scoping conversation is covered: `openrouter_client.py` (Task 1, rename+rewrite), `config.py`/`.env.example` (Task 2), `agent_factory.py` (Task 3), `report_builder_service.py` (Task 4), `build_analysis_plan.py` (Task 5), `chatbot_service.py` (Task 6), `test_config.py` (Task 7), cleanup + `docs/phase3.md` + `decisions.md` (Task 8). `test_build_analysis_plan.py` was confirmed to need zero changes (Task 5) since it patches at its own module's import site — verified by reading the file, not assumed.

**Placeholder scan:** No TBD/TODO markers; every step has complete, exact code; every test has real assertions, not stubs.

**Type consistency:** `GoogleAIClient.__init__(api_key, model, timeout_seconds)` (Task 1) matches every construction call site in Tasks 3 and 4 exactly (`api_key=`, `model=`, `timeout_seconds=` kwargs, same order/names as the old `OpenRouterClient` calls they replace). `self.last_usage` dict keys (`prompt_tokens`/`completion_tokens`/`total_tokens`, Task 1) match what `agent_factory._record_agent_run` already reads (unchanged, not touched by this plan) and what Task 1's own test asserts. `AGENT_KEY_ATTR`/`FALLBACK_KEY_ATTR` key names (agent name strings: `security`, `performance`, `complexity`, `duplication`, `reliability`, `supervisor`, `chatbot`) are identical across Task 1 and Task 3, matching the existing (untouched) `AGENT_PROMPTS` dict keys in `agent_factory.py`.
