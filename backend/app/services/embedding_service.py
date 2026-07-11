import math

import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.chunks import CodeChunk, EmbeddedChunk

GOOGLE_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
BATCH_SIZE = 32
REQUEST_TIMEOUT_SECONDS = 60

# Gemini Embedding 2 outputs 3072 dims by default; truncating via Matryoshka
# Representation Learning to match the existing Qdrant collections' 1024-dim
# vectors (created under the prior HF/BAAI embedding model). Google's docs
# note dims below 3072 aren't normalized by default, so _l2_normalize below
# is required, not optional, for correct cosine-distance behavior.
EMBEDDING_OUTPUT_DIMENSIONALITY = 1024


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Call Google AI Studio's batchEmbedContents for one batch of texts,
    returning one L2-normalized embedding vector per input in the same order."""
    model = settings.embedding_model
    url = GOOGLE_EMBED_URL.format(model=model)
    headers = {"x-goog-api-key": settings.google_api_key_embedding}
    payload = {
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBEDDING_OUTPUT_DIMENSIONALITY,
            }
            for text in texts
        ]
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AppError(
            "EMBEDDING_FAILED", f"Google AI embedding request failed: {exc}", 502
        ) from exc

    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise AppError(
            "EMBEDDING_FAILED", "Unexpected Google AI embedding response shape.", 502
        )

    try:
        return [_l2_normalize(item["values"]) for item in embeddings]
    except (KeyError, TypeError) as exc:
        raise AppError(
            "EMBEDDING_FAILED", f"Unexpected Google AI embedding response shape: {exc}", 502
        ) from exc


def embed_chunks(chunks: list[CodeChunk], chunk_ids: list[str]) -> list[EmbeddedChunk]:
    """Generate embeddings for `chunks` via Google AI Studio's Gemini Embedding 2 model.

    `chunk_ids` must be the Supabase-assigned chunk id (as strings) in the
    same order as `chunks`, used to populate `EmbeddedChunk.chunk_id`.
    """
    if not chunks:
        return []
    if not settings.google_api_key_embedding:
        raise AppError("EMBEDDING_FAILED", "GOOGLE_API_KEY_EMBEDDING is not configured.", 500)

    embedded: list[EmbeddedChunk] = []

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        batch_ids = chunk_ids[start : start + BATCH_SIZE]
        vectors = _embed_batch([c.content for c in batch])

        for chunk, chunk_id, vector in zip(batch, batch_ids, vectors):
            embedded.append(
                EmbeddedChunk(
                    chunk_id=chunk_id,
                    vector=vector,
                    payload={
                        "scan_id": str(chunk.scan_id),
                        "file_id": str(chunk.file_id),
                        "symbol_id": str(chunk.symbol_id) if chunk.symbol_id else None,
                        "chunk_id": str(chunk_id),
                        "file_path": chunk.file_path,
                        "language": chunk.language,
                        "chunk_type": chunk.chunk_type,
                        "symbol_name": chunk.symbol_name,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                    },
                )
            )

    return embedded


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of free-text strings (e.g. agent tool search queries)
    via the same Google AI Studio embedding model used for chunk embeddings."""
    if not texts:
        return []
    if not settings.google_api_key_embedding:
        raise AppError("EMBEDDING_FAILED", "GOOGLE_API_KEY_EMBEDDING is not configured.", 500)

    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        vectors.extend(_embed_batch(batch))
    return vectors


def embed_text(text: str) -> list[float]:
    """Embed a single free-text string (e.g. an agent tool's search query)."""
    vectors = embed_texts([text])
    return vectors[0] if vectors else []
