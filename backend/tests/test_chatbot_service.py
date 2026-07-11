from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
import respx

from app.schemas.chat import ChatMessageRecord
from app.services.chatbot_service import answer_question, classify_question


@pytest.mark.asyncio
@respx.mock
async def test_classify_question_file_specific():
    """Test that classify_question returns 'file_specific' for file-related questions."""
    # Mock Google AI API to return "file_specific"
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    ).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "file_specific"}]}}]}
        )
    )

    with patch("app.services.chatbot_service.build_llm_client") as mock_build:
        from app.services.google_ai_client import GoogleAIClient

        mock_client = GoogleAIClient(api_key="test-key", model="test-model")
        mock_build.return_value = mock_client

        result = await classify_question("What security issues are in auth.py?")
        assert result == "file_specific"


@pytest.mark.asyncio
@respx.mock
async def test_classify_question_general():
    """Test that classify_question returns 'general' for general questions."""
    # Mock Google AI API to return "general"
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    ).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "general"}]}}]}
        )
    )

    with patch("app.services.chatbot_service.build_llm_client") as mock_build:
        from app.services.google_ai_client import GoogleAIClient

        mock_client = GoogleAIClient(api_key="test-key", model="test-model")
        mock_build.return_value = mock_client

        result = await classify_question("What is the overall code quality?")
        assert result == "general"


@pytest.mark.asyncio
@respx.mock
async def test_classify_question_malformed_response_defaults_to_general():
    """Test that classify_question defaults to 'general' on unexpected LLM response."""
    # Mock Google AI API to return an unexpected response
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": "something_unexpected"}]}}
                ]
            },
        )
    )

    with patch("app.services.chatbot_service.build_llm_client") as mock_build:
        from app.services.google_ai_client import GoogleAIClient

        mock_client = GoogleAIClient(api_key="test-key", model="test-model")
        mock_build.return_value = mock_client

        result = await classify_question("Random question")
        assert result == "general"


@pytest.mark.asyncio
async def test_answer_question_appends_user_and_assistant_messages():
    """Test that answer_question appends both user and assistant messages."""
    scan_id = str(uuid4())
    session_id = str(uuid4())
    question = "What are the security findings?"

    # Mock dependencies
    mock_user_msg = ChatMessageRecord(
        id=uuid4(),
        session_id=uuid4(),
        role="user",
        content=question,
        sources=[],
        created_at=datetime.now(),
    )
    mock_assistant_msg = ChatMessageRecord(
        id=uuid4(),
        session_id=uuid4(),
        role="assistant",
        content="Based on the scan...",
        sources=[{"finding_id": "f1"}],
        created_at=datetime.now(),
    )

    with patch("app.services.chatbot_service.append_message") as mock_append, \
         patch("app.services.chatbot_service.classify_question", new_callable=AsyncMock) as mock_classify, \
         patch("app.services.chatbot_service.retrieve_relevant_docs", new_callable=AsyncMock) as mock_retrieve, \
         patch("app.services.chatbot_service.build_context_block") as mock_build_context, \
         patch("app.services.chatbot_service.build_llm_client") as mock_build_client:

        # Setup mocks
        mock_append.side_effect = [mock_user_msg, mock_assistant_msg]
        mock_classify.return_value = "general"
        mock_retrieve.return_value = [
            {
                "text": "Finding text",
                "source_type": "finding",
                "payload": {"finding_id": "f1"},
                "score": 0.9,
            }
        ]
        mock_build_context.return_value = "Context block"

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="Based on the scan...")
        mock_build_client.return_value = mock_llm

        result = await answer_question(scan_id, session_id, question)

        # Verify append_message called twice (user + assistant)
        assert mock_append.call_count == 2
        
        # First call: user message
        first_call = mock_append.call_args_list[0]
        # Check positional args (session_id is first positional arg in the call)
        assert len(first_call.args) >= 1
        assert first_call.args[0] == session_id
        # Check keyword args
        assert first_call.kwargs.get("role") == "user"
        assert first_call.kwargs.get("content") == question
        assert first_call.kwargs.get("sources") is None

        # Second call: assistant message with sources
        second_call = mock_append.call_args_list[1]
        assert len(second_call.args) >= 1
        assert second_call.args[0] == session_id
        assert second_call.kwargs.get("role") == "assistant"
        assert second_call.kwargs.get("content") == "Based on the scan..."
        assert second_call.kwargs.get("sources") == [{"finding_id": "f1"}]

        # Verify returned value is assistant message
        assert result == mock_assistant_msg


@pytest.mark.asyncio
async def test_answer_question_file_specific_calls_graph_context():
    """Test that answer_question calls get_context_for_file when question is file-specific."""
    scan_id = str(uuid4())
    session_id = str(uuid4())
    question = "What are the issues in auth.py?"

    mock_user_msg = ChatMessageRecord(
        id=uuid4(),
        session_id=uuid4(),
        role="user",
        content=question,
        sources=[],
        created_at=datetime.now(),
    )
    mock_assistant_msg = ChatMessageRecord(
        id=uuid4(),
        session_id=uuid4(),
        role="assistant",
        content="Answer",
        sources=[],
        created_at=datetime.now(),
    )

    with patch("app.services.chatbot_service.append_message") as mock_append, \
         patch("app.services.chatbot_service.classify_question", new_callable=AsyncMock) as mock_classify, \
         patch("app.services.chatbot_service.retrieve_relevant_docs", new_callable=AsyncMock) as mock_retrieve, \
         patch("app.services.chatbot_service.get_context_for_file", new_callable=AsyncMock) as mock_graph, \
         patch("app.services.chatbot_service.build_context_block") as mock_build_context, \
         patch("app.services.chatbot_service.build_llm_client") as mock_build_client:

        mock_append.side_effect = [mock_user_msg, mock_assistant_msg]
        mock_classify.return_value = "file_specific"
        mock_retrieve.return_value = []
        mock_graph.return_value = {"imports": [], "symbols": []}
        mock_build_context.return_value = "Context"

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="Answer")
        mock_build_client.return_value = mock_llm

        await answer_question(scan_id, session_id, question)

        # Verify get_context_for_file was called with extracted file path
        mock_graph.assert_called_once()
        assert mock_graph.call_args[0][0] == scan_id
        # Should extract "auth.py" from the question
        assert "auth.py" in mock_graph.call_args[0][1]


@pytest.mark.asyncio
async def test_answer_question_general_skips_graph_context():
    """Test that answer_question does NOT call get_context_for_file for general questions."""
    scan_id = str(uuid4())
    session_id = str(uuid4())
    question = "What is the overall risk score?"

    mock_user_msg = ChatMessageRecord(
        id=uuid4(),
        session_id=uuid4(),
        role="user",
        content=question,
        sources=[],
        created_at=datetime.now(),
    )
    mock_assistant_msg = ChatMessageRecord(
        id=uuid4(),
        session_id=uuid4(),
        role="assistant",
        content="Answer",
        sources=[],
        created_at=datetime.now(),
    )

    with patch("app.services.chatbot_service.append_message") as mock_append, \
         patch("app.services.chatbot_service.classify_question", new_callable=AsyncMock) as mock_classify, \
         patch("app.services.chatbot_service.retrieve_relevant_docs", new_callable=AsyncMock) as mock_retrieve, \
         patch("app.services.chatbot_service.get_context_for_file", new_callable=AsyncMock) as mock_graph, \
         patch("app.services.chatbot_service.build_context_block") as mock_build_context, \
         patch("app.services.chatbot_service.build_llm_client") as mock_build_client:

        mock_append.side_effect = [mock_user_msg, mock_assistant_msg]
        mock_classify.return_value = "general"
        mock_retrieve.return_value = []
        mock_build_context.return_value = "Context"

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="Answer")
        mock_build_client.return_value = mock_llm

        await answer_question(scan_id, session_id, question)

        # Verify get_context_for_file was NOT called
        mock_graph.assert_not_called()
