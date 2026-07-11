"""Service for RAG chatbot question answering and classification."""

import re

from app.schemas.chat import ChatMessageRecord
from app.services.chat_session_service import append_message
from app.services.graph_context_service import get_context_for_file
from app.services.google_ai_client import build_llm_client
from app.services.rag_retrieval_service import retrieve_relevant_docs
from app.services.source_builder_service import build_context_block


async def classify_question(question: str) -> str:
    """Classify a user's question as file-specific or general.

    Uses an LLM to determine if the question references a specific file
    (file_specific) or is a general query about the codebase (general).

    Args:
        question: The user's question text

    Returns:
        Either "file_specific" or "general"
    """
    system_prompt = """You are a question classifier for a code analysis chatbot.
Your task is to determine if a user's question is about a specific file or a general question.

Respond with EXACTLY ONE of these two words:
- "file_specific" if the question mentions a specific file path or filename (e.g., "auth.py", "src/utils.ts", "main.go")
- "general" if the question is about overall code quality, patterns, or does not mention a specific file

Examples:
- "What security issues are in auth.py?" -> file_specific
- "What are the security issues?" -> general
- "How complex is src/utils.ts?" -> file_specific
- "What is the overall code quality?" -> general

Respond with only one word: "file_specific" or "general"."""

    client = build_llm_client("chatbot")
    response = await client.complete(system=system_prompt, user=question)

    # Parse response defensively - normalize and check for "file_specific"
    normalized = response.strip().lower()
    if "file_specific" in normalized:
        return "file_specific"
    return "general"


def _extract_file_path(question: str) -> str | None:
    """Extract a file path from a question using heuristics.

    Looks for common file patterns:
    - Extensions: .py, .ts, .tsx, .js, .jsx, .go, .java, .rb, .cpp, .c, .h, .rs
    - Path-like patterns with / or backslash followed by extension
    - Bare filenames with extensions

    Args:
        question: The user's question text

    Returns:
        Extracted file path if found, None otherwise
    """
    # Common file extensions for code files
    extensions = r'\.(py|ts|tsx|js|jsx|go|java|rb|cpp|c|h|hpp|rs|cs|php|swift|kt|m|scala)'
    
    # Pattern: optional path components + filename with extension
    # Matches: auth.py, src/auth.py, src/utils/auth.py, etc.
    pattern = r'(?:[\w\-\.\/\\]+[\\/])?[\w\-\.]+' + extensions
    
    match = re.search(pattern, question)
    if match:
        return match.group(0)
    
    return None


async def answer_question(scan_id: str, session_id: str, question: str) -> ChatMessageRecord:
    """Answer a user's question using RAG over the scanned repository.

    Process:
    1. Persist user message
    2. Classify question (file-specific vs general)
    3. Retrieve relevant documents from Qdrant
    4. If file-specific, extract file path and get graph context
    5. Build context block from docs + graph context
    6. Generate answer via LLM
    7. Persist assistant message with sources
    8. Return assistant message record

    Args:
        scan_id: The scan UUID
        session_id: The chat session UUID
        question: The user's question

    Returns:
        ChatMessageRecord: The assistant's message record with sources
    """
    # Step 1: Persist user message
    append_message(session_id, role="user", content=question, sources=None)

    # Step 2: Classify question
    category = await classify_question(question)

    # Step 3: Retrieve relevant documents
    docs = await retrieve_relevant_docs(scan_id, question)

    # Step 4: Get graph context if file-specific
    graph_context = None
    if category == "file_specific":
        file_path = _extract_file_path(question)
        if file_path:
            graph_context = await get_context_for_file(scan_id, file_path)

    # Step 5: Build context block
    context_block = build_context_block(docs, graph_context)

    # Step 6: Generate answer via LLM
    system_prompt = """You are a code quality analysis assistant helping developers understand scan results.

Your responsibilities:
- Answer questions ONLY using the retrieved scan context provided
- Mention when specific context is unavailable or unclear
- Include source references (file paths, function names) from the context
- Prefer exact file paths and symbol names from the retrieved context
- Avoid making unsupported claims about code not in the context
- Give prioritized, actionable recommendations when relevant

You must NOT:
- Invent files, findings, or code that was not retrieved
- Assume code structure beyond what is provided in context
- Re-run analysis or suggest running new agents
- Modify repository code

Be concise, accurate, and helpful. If you cannot answer based on available context, say so clearly."""

    user_prompt = f"""{context_block}

User Question:
{question}

Please provide a helpful answer based on the context above."""

    client = build_llm_client("chatbot")
    answer_text = await client.complete(system=system_prompt, user=user_prompt)

    # Step 8: Extract sources from docs
    sources = [doc["payload"] for doc in docs]

    # Step 9: Persist assistant message
    assistant_message = append_message(
        session_id, role="assistant", content=answer_text, sources=sources
    )

    # Step 10: Return assistant message
    return assistant_message
