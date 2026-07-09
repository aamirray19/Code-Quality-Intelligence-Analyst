import pytest
from datetime import datetime
from uuid import UUID
from pydantic import ValidationError

from app.schemas.chat import ChatSessionRecord, ChatMessageRecord, ChatMessageCreate


def test_chat_session_record_valid():
    """Test creating a valid ChatSessionRecord instance."""
    scan_id = UUID("12345678-1234-5678-1234-567812345678")
    session_id = UUID("87654321-4321-8765-4321-876543218765")
    created_at = datetime.now()
    updated_at = datetime.now()
    
    session = ChatSessionRecord(
        id=session_id,
        scan_id=scan_id,
        title="Analysis Session",
        created_at=created_at,
        updated_at=updated_at,
    )
    
    assert session.id == session_id
    assert session.scan_id == scan_id
    assert session.title == "Analysis Session"
    assert session.created_at == created_at
    assert session.updated_at == updated_at


def test_chat_session_record_with_none_title():
    """Test creating a ChatSessionRecord with None title."""
    scan_id = UUID("12345678-1234-5678-1234-567812345678")
    session_id = UUID("87654321-4321-8765-4321-876543218765")
    created_at = datetime.now()
    updated_at = datetime.now()
    
    session = ChatSessionRecord(
        id=session_id,
        scan_id=scan_id,
        title=None,
        created_at=created_at,
        updated_at=updated_at,
    )
    
    assert session.title is None


def test_chat_session_record_missing_scan_id():
    """Test that missing scan_id raises ValidationError."""
    with pytest.raises(ValidationError):
        ChatSessionRecord(
            id=UUID("87654321-4321-8765-4321-876543218765"),
            # missing scan_id
            title="Analysis Session",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )


def test_chat_message_record_valid():
    """Test creating a valid ChatMessageRecord instance."""
    session_id = UUID("12345678-1234-5678-1234-567812345678")
    message_id = UUID("87654321-4321-8765-4321-876543218765")
    created_at = datetime.now()
    
    message = ChatMessageRecord(
        id=message_id,
        session_id=session_id,
        role="user",
        content="What are the security vulnerabilities?",
        sources=[],
        created_at=created_at,
    )
    
    assert message.id == message_id
    assert message.session_id == session_id
    assert message.role == "user"
    assert message.content == "What are the security vulnerabilities?"
    assert message.sources == []
    assert message.created_at == created_at


def test_chat_message_record_with_sources():
    """Test ChatMessageRecord with sources list."""
    sources = [
        {"file_id": "abc123", "line": 42},
        {"file_id": "def456", "line": 100},
    ]
    
    message = ChatMessageRecord(
        id=UUID("87654321-4321-8765-4321-876543218765"),
        session_id=UUID("12345678-1234-5678-1234-567812345678"),
        role="assistant",
        content="Found vulnerabilities in these files.",
        sources=sources,
        created_at=datetime.now(),
    )
    
    assert message.sources == sources


def test_chat_message_record_missing_session_id():
    """Test that missing session_id raises ValidationError."""
    with pytest.raises(ValidationError):
        ChatMessageRecord(
            id=UUID("87654321-4321-8765-4321-876543218765"),
            # missing session_id
            role="user",
            content="What are the vulnerabilities?",
            sources=[],
            created_at=datetime.now(),
        )


def test_chat_message_record_missing_role():
    """Test that missing role raises ValidationError."""
    with pytest.raises(ValidationError):
        ChatMessageRecord(
            id=UUID("87654321-4321-8765-4321-876543218765"),
            session_id=UUID("12345678-1234-5678-1234-567812345678"),
            # missing role
            content="What are the vulnerabilities?",
            sources=[],
            created_at=datetime.now(),
        )


def test_chat_message_create_valid():
    """Test creating a valid ChatMessageCreate instance."""
    create_msg = ChatMessageCreate(
        content="What security issues exist?"
    )
    
    assert create_msg.content == "What security issues exist?"


def test_chat_message_create_missing_content():
    """Test that missing content raises ValidationError."""
    with pytest.raises(ValidationError):
        ChatMessageCreate()


def test_chat_message_create_empty_content():
    """Test that empty content is allowed."""
    create_msg = ChatMessageCreate(content="")
    assert create_msg.content == ""
