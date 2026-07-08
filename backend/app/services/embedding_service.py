import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.chunks import CodeChunk, EmbeddedChunk

HF_INFERENCE_URL = "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
BATCH_SIZE = 32
REQUEST_TIMEOUT_SECONDS = 60


def _mean_pool(vectors: list[list[float]]) -> list[float]:
    """Mean-pool token-level embeddings into a single sentence vector."""
    if not vectors:
        return []
    dim = len(vectors[0])
    sums = [0.0] * dim
    for vector in vectors:
        for i, value in enumerate(vector):
            sums[i] += value
    return [s / len(vectors) for s in sums]


def _normalize_embedding(raw: object) -> list[float]:
    """Normalize a single HF response item into a flat embedding vector.

    The HF feature-extraction endpoint may return either an already-pooled
    sentence vector (`list[float]`) or per-token vectors (`list[list[float]]`),
    depending on the model/pipeline tag, so both shapes are handled here.
    """
    if not isinstance(raw, list) or not raw:
        raise ValueError("Empty or malformed embedding response item")
    if isinstance(raw[0], list):
        return _mean_pool(raw)
    return raw


def embed_chunks(chunks: list[CodeChunk], chunk_ids: list[str]) -> list[EmbeddedChunk]:
    """Generate embeddings for `chunks` via the HuggingFace Inference API.

    `chunk_ids` must be the Supabase-assigned chunk id (as strings) in the
    same order as `chunks`, used to populate `EmbeddedChunk.chunk_id`.
    """
    if not chunks:
        return []
    if not settings.hf_api_token:
        raise AppError("EMBEDDING_FAILED", "HF_API_TOKEN is not configured.", 500)

    url = HF_INFERENCE_URL.format(model=settings.embedding_model)
    headers = {"Authorization": f"Bearer {settings.hf_api_token}"}

    embedded: list[EmbeddedChunk] = []

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            batch_ids = chunk_ids[start : start + BATCH_SIZE]
            inputs = [c.content for c in batch]

            try:
                response = client.post(
                    url,
                    headers=headers,
                    json={"inputs": inputs, "options": {"wait_for_model": True}},
                )
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise AppError(
                    "EMBEDDING_FAILED", f"HuggingFace embedding request failed: {exc}", 502
                ) from exc

            if not isinstance(data, list) or len(data) != len(batch):
                raise AppError(
                    "EMBEDDING_FAILED",
                    "Unexpected HuggingFace embedding response shape.",
                    502,
                )

            for chunk, chunk_id, raw_vector in zip(batch, batch_ids, data):
                try:
                    vector = _normalize_embedding(raw_vector)
                except ValueError as exc:
                    raise AppError("EMBEDDING_FAILED", str(exc), 502) from exc

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
    via the same HuggingFace Inference API used for chunk embeddings."""
    if not texts:
        return []
    if not settings.hf_api_token:
        raise AppError("EMBEDDING_FAILED", "HF_API_TOKEN is not configured.", 500)

    url = HF_INFERENCE_URL.format(model=settings.embedding_model)
    headers = {"Authorization": f"Bearer {settings.hf_api_token}"}
    vectors: list[list[float]] = []

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            try:
                response = client.post(
                    url, headers=headers, json={"inputs": batch, "options": {"wait_for_model": True}}
                )
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise AppError(
                    "EMBEDDING_FAILED", f"HuggingFace embedding request failed: {exc}", 502
                ) from exc

            if not isinstance(data, list) or len(data) != len(batch):
                raise AppError(
                    "EMBEDDING_FAILED", "Unexpected HuggingFace embedding response shape.", 502
                )

            for raw_vector in data:
                try:
                    vectors.append(_normalize_embedding(raw_vector))
                except ValueError as exc:
                    raise AppError("EMBEDDING_FAILED", str(exc), 502) from exc

    return vectors


def embed_text(text: str) -> list[float]:
    """Embed a single free-text string (e.g. an agent tool's search query)."""
    vectors = embed_texts([text])
    return vectors[0] if vectors else []
