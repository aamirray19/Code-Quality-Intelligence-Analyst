import json

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
@respx.mock
async def test_complete_skips_thought_parts_and_returns_the_real_answer():
    # Thinking-enabled models can return a reasoning-trace part ahead of the
    # real answer, marked "thought": true. parts[0] alone would be the trace.
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"text": "reasoning about the answer...", "thought": True},
                                {"text": "[]"},
                            ],
                        }
                    }
                ],
            },
        )
    )
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    result = await client.complete(system="sys", user="user")
    assert result == "[]"


@pytest.mark.asyncio
@respx.mock
async def test_complete_never_sends_thinking_config():
    # Gemma models reject thinkingConfig outright with 400 "Thinking budget
    # is not supported for this model." (confirmed live against the real
    # API) -- it must never be sent, regardless of model. Response-shape
    # defense (test_complete_skips_thought_parts_and_returns_the_real_answer
    # above) is the only way thinking output is handled.
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}]}
        )
    )
    client = GoogleAIClient(api_key="test-key", model="gemini-2.5-flash")
    await client.complete(system="sys", user="user")

    request = respx.calls.last.request
    body = json.loads(request.content)
    assert "thinkingConfig" not in body["generationConfig"]


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
