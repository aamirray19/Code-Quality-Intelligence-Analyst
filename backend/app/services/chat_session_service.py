from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.chat import ChatMessageRecord, ChatSessionRecord


def create_session(scan_id: str, title: str | None) -> ChatSessionRecord:
    """Create a new chat session.

    Args:
        scan_id: The scan UUID
        title: Optional session title

    Returns:
        ChatSessionRecord: The created session record
    """
    client = get_supabase_client()
    payload = {"scan_id": scan_id, "title": title}
    result = client.table("chat_sessions").insert(payload).execute()
    row = result.data[0]
    return ChatSessionRecord(**row)


def list_sessions(scan_id: str) -> list[ChatSessionRecord]:
    """List all chat sessions for a scan.

    Args:
        scan_id: The scan UUID

    Returns:
        list[ChatSessionRecord]: List of session records, ordered by created_at ascending
    """
    client = get_supabase_client()
    result = (
        client.table("chat_sessions")
        .select("*")
        .eq("scan_id", scan_id)
        .order("created_at")
        .execute()
    )
    if not result.data:
        return []
    return [ChatSessionRecord(**row) for row in result.data]


def get_session(session_id: str | UUID) -> ChatSessionRecord | None:
    """Retrieve a chat session by ID.

    Args:
        session_id: The session UUID (accepts str or UUID)

    Returns:
        ChatSessionRecord | None: The session if found, None otherwise
    """
    client = get_supabase_client()
    result = client.table("chat_sessions").select("*").eq("id", str(session_id)).execute()
    if not result.data:
        return None
    return ChatSessionRecord(**result.data[0])


def append_message(
    session_id: str | UUID, role: str, content: str, sources: list | None
) -> ChatMessageRecord:
    """Append a message to a chat session.

    Auto-generates session title from first 50 chars of content on the first user message
    if the session title is currently None.

    Args:
        session_id: The session UUID (accepts str or UUID)
        role: Message role ('user' or 'assistant')
        content: Message content
        sources: Optional list of source references (defaults to empty list)

    Returns:
        ChatMessageRecord: The created message record
    """
    client = get_supabase_client()

    # Default sources to empty list if None
    if sources is None:
        sources = []

    # Insert the message
    payload = {
        "session_id": str(session_id),
        "role": role,
        "content": content,
        "sources": sources,
    }
    result = client.table("chat_messages").insert(payload).execute()
    row = result.data[0]

    # Auto-generate title from first user message if title is None
    if role == "user":
        session = get_session(session_id)
        if session and session.title is None:
            auto_title = content[:50]
            client.table("chat_sessions").update({"title": auto_title}).eq(
                "id", str(session_id)
            ).execute()

    return ChatMessageRecord(**row)


def list_messages(session_id: str | UUID) -> list[ChatMessageRecord]:
    """List all messages in a chat session.

    Args:
        session_id: The session UUID (accepts str or UUID)

    Returns:
        list[ChatMessageRecord]: List of message records, ordered by created_at ascending
    """
    client = get_supabase_client()
    result = (
        client.table("chat_messages")
        .select("*")
        .eq("session_id", str(session_id))
        .order("created_at")
        .execute()
    )
    if not result.data:
        return []
    return [ChatMessageRecord(**row) for row in result.data]
