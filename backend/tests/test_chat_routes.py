from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ChatMessageRecord, ChatSessionRecord
from app.schemas.scans import ScanRecord

client = TestClient(app)


def _sample_scan_record(scan_id, status="analyzed"):
    now = datetime.now(timezone.utc)
    return ScanRecord(
        id=scan_id,
        github_url="https://github.com/owner/repo",
        repo_owner="owner",
        repo_name="repo",
        repo_full_name="owner/repo",
        branch="main",
        default_branch="main",
        clone_url="https://github.com/owner/repo.git",
        html_url="https://github.com/owner/repo",
        repo_size_kb=1277,
        status=status,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def _sample_chat_session_record(session_id, scan_id, title=None):
    now = datetime.now(timezone.utc)
    return ChatSessionRecord(
        id=session_id,
        scan_id=scan_id,
        title=title,
        created_at=now,
        updated_at=now,
    )


def _sample_chat_message_record(message_id, session_id, role="user", content="Hello"):
    now = datetime.now(timezone.utc)
    return ChatMessageRecord(
        id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        sources=[],
        created_at=now,
    )


# POST /scans/{scan_id}/chat/sessions tests
def test_create_chat_session_scan_not_found():
    scan_id = uuid4()
    with patch("app.api.routes.chat.scan_service.get_scan", return_value=None):
        response = client.post(f"/scans/{scan_id}/chat/sessions", json={})

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_create_chat_session_success_no_title():
    scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    session_record = _sample_chat_session_record(session_id, scan_id, title=None)

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.create_session", return_value=session_record):
        response = client.post(f"/scans/{scan_id}/chat/sessions", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(session_id)
    assert body["scan_id"] == str(scan_id)
    assert body["title"] is None


def test_create_chat_session_success_with_title():
    scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    session_record = _sample_chat_session_record(session_id, scan_id, title="My Session")

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.create_session", return_value=session_record):
        response = client.post(f"/scans/{scan_id}/chat/sessions", json={"title": "My Session"})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My Session"


# GET /scans/{scan_id}/chat/sessions tests
def test_list_chat_sessions_scan_not_found():
    scan_id = uuid4()
    with patch("app.api.routes.chat.scan_service.get_scan", return_value=None):
        response = client.get(f"/scans/{scan_id}/chat/sessions")

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_list_chat_sessions_success():
    scan_id = uuid4()
    session_id1 = uuid4()
    session_id2 = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    sessions = [
        _sample_chat_session_record(session_id1, scan_id, title="Session 1"),
        _sample_chat_session_record(session_id2, scan_id, title="Session 2"),
    ]

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.list_sessions", return_value=sessions):
        response = client.get(f"/scans/{scan_id}/chat/sessions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == str(session_id1)
    assert body[1]["id"] == str(session_id2)


# POST /scans/{scan_id}/chat/sessions/{session_id}/messages tests
def test_create_chat_message_scan_not_found():
    scan_id = uuid4()
    session_id = uuid4()
    with patch("app.api.routes.chat.scan_service.get_scan", return_value=None):
        response = client.post(
            f"/scans/{scan_id}/chat/sessions/{session_id}/messages",
            json={"content": "Hello"}
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_create_chat_message_session_not_found():
    scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="reported")

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.get_session", return_value=None):
        response = client.post(
            f"/scans/{scan_id}/chat/sessions/{session_id}/messages",
            json={"content": "Hello"}
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "CHAT_SESSION_NOT_FOUND"


def test_create_chat_message_session_scan_mismatch():
    scan_id = uuid4()
    other_scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="reported")
    session_record = _sample_chat_session_record(session_id, other_scan_id)

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.get_session", return_value=session_record):
        response = client.post(
            f"/scans/{scan_id}/chat/sessions/{session_id}/messages",
            json={"content": "Hello"}
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "CHAT_SESSION_NOT_FOUND"


def test_create_chat_message_success():
    scan_id = uuid4()
    session_id = uuid4()
    message_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="reported")
    session_record = _sample_chat_session_record(session_id, scan_id)
    message_record = _sample_chat_message_record(message_id, session_id, role="assistant", content="Answer")

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.get_session", return_value=session_record), \
         patch("app.api.routes.chat.chatbot_service.answer_question", new_callable=AsyncMock, return_value=message_record):
        response = client.post(
            f"/scans/{scan_id}/chat/sessions/{session_id}/messages",
            json={"content": "Hello"}
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(message_id)
    assert body["role"] == "assistant"
    assert body["content"] == "Answer"


def test_create_chat_message_scan_not_reported():
    scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record):
        response = client.post(
            f"/scans/{scan_id}/chat/sessions/{session_id}/messages",
            json={"content": "Hello"}
        )

    assert response.status_code == 409
    assert response.json()["error_code"] == "SCAN_NOT_COMPLETED"


# GET /scans/{scan_id}/chat/sessions/{session_id}/messages tests
def test_list_chat_messages_scan_not_found():
    scan_id = uuid4()
    session_id = uuid4()
    with patch("app.api.routes.chat.scan_service.get_scan", return_value=None):
        response = client.get(f"/scans/{scan_id}/chat/sessions/{session_id}/messages")

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_list_chat_messages_session_not_found():
    scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.get_session", return_value=None):
        response = client.get(f"/scans/{scan_id}/chat/sessions/{session_id}/messages")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CHAT_SESSION_NOT_FOUND"


def test_list_chat_messages_session_scan_mismatch():
    scan_id = uuid4()
    other_scan_id = uuid4()
    session_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    session_record = _sample_chat_session_record(session_id, other_scan_id)

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.get_session", return_value=session_record):
        response = client.get(f"/scans/{scan_id}/chat/sessions/{session_id}/messages")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CHAT_SESSION_NOT_FOUND"


def test_list_chat_messages_success():
    scan_id = uuid4()
    session_id = uuid4()
    message_id1 = uuid4()
    message_id2 = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    session_record = _sample_chat_session_record(session_id, scan_id)
    messages = [
        _sample_chat_message_record(message_id1, session_id, role="user", content="Hello"),
        _sample_chat_message_record(message_id2, session_id, role="assistant", content="Hi"),
    ]

    with patch("app.api.routes.chat.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.chat.chat_session_service.get_session", return_value=session_record), \
         patch("app.api.routes.chat.chat_session_service.list_messages", return_value=messages):
        response = client.get(f"/scans/{scan_id}/chat/sessions/{session_id}/messages")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["role"] == "user"
    assert body[1]["role"] == "assistant"
