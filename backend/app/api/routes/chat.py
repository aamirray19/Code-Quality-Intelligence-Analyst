from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import AppError
from app.schemas.chat import ChatMessageCreate, ChatMessageRecord, ChatSessionRecord
from app.services import chat_session_service, chatbot_service, scan_service

router = APIRouter()


class CreateChatSessionRequest(BaseModel):
    title: str | None = None


@router.post("/scans/{scan_id}/chat/sessions", status_code=201, response_model=ChatSessionRecord)
def create_chat_session(scan_id: UUID, request: CreateChatSessionRequest) -> ChatSessionRecord:
    """Create a new chat session for a scan.

    Args:
        scan_id: The scan UUID
        request: Request body with optional title

    Returns:
        ChatSessionRecord: The created session record

    Raises:
        AppError: SCAN_NOT_FOUND (404) if scan doesn't exist
    """
    # Check scan exists
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    # Create the session
    session = chat_session_service.create_session(str(scan_id), request.title)
    return session


@router.get("/scans/{scan_id}/chat/sessions", response_model=list[ChatSessionRecord])
def list_chat_sessions(scan_id: UUID) -> list[ChatSessionRecord]:
    """List all chat sessions for a scan.

    Args:
        scan_id: The scan UUID

    Returns:
        list[ChatSessionRecord]: List of session records

    Raises:
        AppError: SCAN_NOT_FOUND (404) if scan doesn't exist
    """
    # Check scan exists
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    # List sessions
    sessions = chat_session_service.list_sessions(str(scan_id))
    return sessions


@router.post(
    "/scans/{scan_id}/chat/sessions/{session_id}/messages",
    status_code=201,
    response_model=ChatMessageRecord,
)
async def create_chat_message(
    scan_id: UUID, session_id: UUID, request: ChatMessageCreate
) -> ChatMessageRecord:
    """Create a new message in a chat session and get an AI-generated response.

    Args:
        scan_id: The scan UUID
        session_id: The session UUID
        request: Request body with message content

    Returns:
        ChatMessageRecord: The assistant's response message

    Raises:
        AppError: SCAN_NOT_FOUND (404) if scan doesn't exist
        AppError: CHAT_SESSION_NOT_FOUND (404) if session doesn't exist or scan_id mismatch
    """
    # Check scan exists
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    # Check session exists and belongs to the scan
    session = chat_session_service.get_session(session_id)
    if session is None or session.scan_id != scan_id:
        raise AppError("CHAT_SESSION_NOT_FOUND", "Chat session not found.", 404)

    # Get answer from chatbot service (returns assistant message)
    assistant_message = await chatbot_service.answer_question(
        str(scan_id), str(session_id), request.content
    )
    return assistant_message


@router.get(
    "/scans/{scan_id}/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessageRecord],
)
def list_chat_messages(scan_id: UUID, session_id: UUID) -> list[ChatMessageRecord]:
    """List all messages in a chat session.

    Args:
        scan_id: The scan UUID
        session_id: The session UUID

    Returns:
        list[ChatMessageRecord]: List of message records

    Raises:
        AppError: SCAN_NOT_FOUND (404) if scan doesn't exist
        AppError: CHAT_SESSION_NOT_FOUND (404) if session doesn't exist or scan_id mismatch
    """
    # Check scan exists
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    # Check session exists and belongs to the scan
    session = chat_session_service.get_session(session_id)
    if session is None or session.scan_id != scan_id:
        raise AppError("CHAT_SESSION_NOT_FOUND", "Chat session not found.", 404)

    # List messages
    messages = chat_session_service.list_messages(session_id)
    return messages
