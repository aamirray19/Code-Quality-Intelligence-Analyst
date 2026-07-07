from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.chat import ChatMessageRecord, ChatSessionRecord
from app.services import chat_session_service


@pytest.fixture
def mock_supabase():
    with patch("app.services.chat_session_service.get_supabase_client") as mock:
        yield mock.return_value


def test_create_session_with_title(mock_supabase):
    scan_id = str(uuid4())
    title = "Test Session"
    session_id = uuid4()
    now = datetime.now()

    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": str(session_id),
            "scan_id": scan_id,
            "title": title,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result

    result = chat_session_service.create_session(scan_id, title)

    assert isinstance(result, ChatSessionRecord)
    assert str(result.id) == str(session_id)
    assert str(result.scan_id) == scan_id
    assert result.title == title

    mock_supabase.table.assert_called_once_with("chat_sessions")
    mock_supabase.table.return_value.insert.assert_called_once_with(
        {"scan_id": scan_id, "title": title}
    )


def test_create_session_with_none_title(mock_supabase):
    scan_id = str(uuid4())
    session_id = uuid4()
    now = datetime.now()

    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": str(session_id),
            "scan_id": scan_id,
            "title": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result

    result = chat_session_service.create_session(scan_id, None)

    assert isinstance(result, ChatSessionRecord)
    assert str(result.id) == str(session_id)
    assert str(result.scan_id) == scan_id
    assert result.title is None

    mock_supabase.table.assert_called_once_with("chat_sessions")
    mock_supabase.table.return_value.insert.assert_called_once_with(
        {"scan_id": scan_id, "title": None}
    )


def test_list_sessions_returns_records(mock_supabase):
    scan_id = str(uuid4())
    session_id1 = uuid4()
    session_id2 = uuid4()
    now = datetime.now()

    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": str(session_id1),
            "scan_id": scan_id,
            "title": "Session 1",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
        {
            "id": str(session_id2),
            "scan_id": scan_id,
            "title": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    ]
    (
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value
    ) = mock_result

    result = chat_session_service.list_sessions(scan_id)

    assert len(result) == 2
    assert all(isinstance(session, ChatSessionRecord) for session in result)
    assert str(result[0].id) == str(session_id1)
    assert str(result[1].id) == str(session_id2)

    mock_supabase.table.assert_called_once_with("chat_sessions")
    mock_supabase.table.return_value.select.assert_called_once_with("*")
    mock_supabase.table.return_value.select.return_value.eq.assert_called_once_with(
        "scan_id", scan_id
    )
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.assert_called_once_with(
        "created_at"
    )


def test_list_sessions_returns_empty_list(mock_supabase):
    scan_id = str(uuid4())

    mock_result = MagicMock()
    mock_result.data = []
    (
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value
    ) = mock_result

    result = chat_session_service.list_sessions(scan_id)

    assert result == []


def test_get_session_found(mock_supabase):
    session_id = str(uuid4())
    scan_id = str(uuid4())
    now = datetime.now()

    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": session_id,
            "scan_id": scan_id,
            "title": "Test Session",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

    result = chat_session_service.get_session(session_id)

    assert isinstance(result, ChatSessionRecord)
    assert str(result.id) == session_id
    assert str(result.scan_id) == scan_id
    assert result.title == "Test Session"

    mock_supabase.table.assert_called_once_with("chat_sessions")
    mock_supabase.table.return_value.select.assert_called_once_with("*")
    mock_supabase.table.return_value.select.return_value.eq.assert_called_once_with(
        "id", session_id
    )


def test_get_session_not_found(mock_supabase):
    session_id = str(uuid4())

    mock_result = MagicMock()
    mock_result.data = []
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

    result = chat_session_service.get_session(session_id)

    assert result is None


def test_append_message_assistant_no_title_update(mock_supabase):
    session_id = str(uuid4())
    message_id = uuid4()
    now = datetime.now()

    mock_message_result = MagicMock()
    mock_message_result.data = [
        {
            "id": str(message_id),
            "session_id": session_id,
            "role": "assistant",
            "content": "This is an assistant response.",
            "sources": ["file1.py", "file2.py"],
            "created_at": now.isoformat(),
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_message_result

    result = chat_session_service.append_message(
        session_id, "assistant", "This is an assistant response.", ["file1.py", "file2.py"]
    )

    assert isinstance(result, ChatMessageRecord)
    assert str(result.id) == str(message_id)
    assert str(result.session_id) == session_id
    assert result.role == "assistant"
    assert result.content == "This is an assistant response."
    assert result.sources == ["file1.py", "file2.py"]

    # Should have inserted message but NOT called get_session or update
    calls = [call[0][0] for call in mock_supabase.table.call_args_list]
    assert calls == ["chat_messages"]


def test_append_message_user_first_message_auto_title(mock_supabase):
    session_id = str(uuid4())
    scan_id = str(uuid4())
    message_id = uuid4()
    now = datetime.now()
    content = "This is a user question that is longer than fifty characters so it should be truncated."

    # Mock message insert
    mock_message_result = MagicMock()
    mock_message_result.data = [
        {
            "id": str(message_id),
            "session_id": session_id,
            "role": "user",
            "content": content,
            "sources": [],
            "created_at": now.isoformat(),
        }
    ]

    # Mock get_session for title check
    mock_get_session_result = MagicMock()
    mock_get_session_result.data = [
        {
            "id": session_id,
            "scan_id": str(scan_id),
            "title": None,  # Title is None, so auto-generate
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]

    # Mock update session
    mock_update_result = MagicMock()
    mock_update_result.data = [
        {
            "id": session_id,
            "scan_id": str(scan_id),
            "title": content[:50],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]

    # Configure mock call order
    mock_table = MagicMock()
    mock_supabase.table.return_value = mock_table

    # First call: insert message
    mock_table.insert.return_value.execute.return_value = mock_message_result

    # Second call: get session to check title
    mock_table.select.return_value.eq.return_value.execute.return_value = mock_get_session_result

    # Third call: update session with title
    mock_table.update.return_value.eq.return_value.execute.return_value = mock_update_result

    result = chat_session_service.append_message(session_id, "user", content, None)

    assert isinstance(result, ChatMessageRecord)
    assert str(result.id) == str(message_id)
    assert result.role == "user"
    assert result.content == content

    # Verify the update was called with the first 50 chars
    expected_title = content[:50]
    mock_table.update.assert_called_once_with({"title": expected_title})


def test_append_message_user_second_message_no_title_update(mock_supabase):
    session_id = str(uuid4())
    scan_id = str(uuid4())
    message_id = uuid4()
    now = datetime.now()
    content = "This is a second user message."

    # Mock message insert
    mock_message_result = MagicMock()
    mock_message_result.data = [
        {
            "id": str(message_id),
            "session_id": session_id,
            "role": "user",
            "content": content,
            "sources": [],
            "created_at": now.isoformat(),
        }
    ]

    # Mock get_session for title check
    mock_get_session_result = MagicMock()
    mock_get_session_result.data = [
        {
            "id": session_id,
            "scan_id": str(scan_id),
            "title": "Existing Title",  # Title already exists
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    ]

    # Configure mock call order
    mock_table = MagicMock()
    mock_supabase.table.return_value = mock_table

    # First call: insert message
    mock_table.insert.return_value.execute.return_value = mock_message_result

    # Second call: get session to check title
    mock_table.select.return_value.eq.return_value.execute.return_value = mock_get_session_result

    result = chat_session_service.append_message(session_id, "user", content, None)

    assert isinstance(result, ChatMessageRecord)
    assert str(result.id) == str(message_id)
    assert result.role == "user"

    # Verify update was NOT called
    mock_table.update.assert_not_called()


def test_append_message_defaults_none_sources_to_empty_list(mock_supabase):
    session_id = str(uuid4())
    message_id = uuid4()
    now = datetime.now()

    mock_message_result = MagicMock()
    mock_message_result.data = [
        {
            "id": str(message_id),
            "session_id": session_id,
            "role": "assistant",
            "content": "Response without sources.",
            "sources": [],
            "created_at": now.isoformat(),
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_message_result

    result = chat_session_service.append_message(
        session_id, "assistant", "Response without sources.", None
    )

    assert result.sources == []
    mock_supabase.table.return_value.insert.assert_called_once_with(
        {
            "session_id": session_id,
            "role": "assistant",
            "content": "Response without sources.",
            "sources": [],
        }
    )


def test_list_messages_returns_records(mock_supabase):
    session_id = str(uuid4())
    message_id1 = uuid4()
    message_id2 = uuid4()
    now = datetime.now()

    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": str(message_id1),
            "session_id": session_id,
            "role": "user",
            "content": "User question",
            "sources": [],
            "created_at": now.isoformat(),
        },
        {
            "id": str(message_id2),
            "session_id": session_id,
            "role": "assistant",
            "content": "Assistant response",
            "sources": ["file1.py"],
            "created_at": now.isoformat(),
        },
    ]
    (
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value
    ) = mock_result

    result = chat_session_service.list_messages(session_id)

    assert len(result) == 2
    assert all(isinstance(msg, ChatMessageRecord) for msg in result)
    assert str(result[0].id) == str(message_id1)
    assert str(result[1].id) == str(message_id2)

    mock_supabase.table.assert_called_once_with("chat_messages")
    mock_supabase.table.return_value.select.assert_called_once_with("*")
    mock_supabase.table.return_value.select.return_value.eq.assert_called_once_with(
        "session_id", session_id
    )
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.assert_called_once_with(
        "created_at"
    )


def test_list_messages_returns_empty_list(mock_supabase):
    session_id = str(uuid4())

    mock_result = MagicMock()
    mock_result.data = []
    (
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value
    ) = mock_result

    result = chat_session_service.list_messages(session_id)

    assert result == []
