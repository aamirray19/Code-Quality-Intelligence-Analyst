import httpx
import pytest
import respx

from app.core.errors import AppError
from app.services.openrouter_client import FakeLLMClient, OpenRouterClient, build_llm_client


@pytest.mark.asyncio
@respx.mock
async def test_complete_returns_message_content():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "[]"}}]}
        )
    )
    client = OpenRouterClient(api_key="test-key", model="deepseek/deepseek-chat-v3-0324")
    result = await client.complete(system="sys", user="user")
    assert result == "[]"


@pytest.mark.asyncio
async def test_complete_raises_when_key_missing():
    client = OpenRouterClient(api_key="", model="deepseek/deepseek-chat-v3-0324")
    with pytest.raises(AppError) as exc_info:
        await client.complete(system="sys", user="user")
    assert exc_info.value.error_code == "LLM_NOT_CONFIGURED"


@pytest.mark.asyncio
@respx.mock
async def test_complete_raises_app_error_on_http_failure():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    client = OpenRouterClient(api_key="test-key", model="deepseek/deepseek-chat-v3-0324")
    with pytest.raises(AppError) as exc_info:
        await client.complete(system="sys", user="user")
    assert exc_info.value.error_code == "LLM_REQUEST_FAILED"


@pytest.mark.asyncio
async def test_fake_llm_client_records_calls():
    fake = FakeLLMClient(response="canned")
    result = await fake.complete(system="sys", user="user")
    assert result == "canned"
    assert fake.calls == [{"system": "sys", "user": "user"}]


def test_build_llm_client_uses_supervisor_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key_supervisor", "sup-key")
    client = build_llm_client("supervisor")
    assert client._api_key == "sup-key"


def test_build_llm_client_uses_chatbot_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key_chatbot", "chatbot-key")
    client = build_llm_client("chatbot")
    assert client._api_key == "chatbot-key"
