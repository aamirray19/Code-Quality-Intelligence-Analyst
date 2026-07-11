from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.errors import AppError
from app.schemas.chunks import CodeChunk, EmbeddedChunk
from app.services.embedding_service import embed_chunks, embed_text, embed_texts

MODULE = "app.services.embedding_service"


def test_embed_texts_calls_google_ai_and_returns_vectors():
    # Already unit-length so it's unchanged by the service's L2 normalization,
    # keeping this assertion a direct equality check.
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"embeddings": [{"values": [1.0, 0.0, 0.0]}]}

    with patch(f"{MODULE}.settings") as settings_mock, patch(f"{MODULE}.httpx.Client") as client_cls_mock:
        settings_mock.google_api_key_embedding = "token"
        settings_mock.embedding_model = "gemini-embedding-2"
        client_instance = client_cls_mock.return_value.__enter__.return_value
        client_instance.post.return_value = fake_response

        result = embed_texts(["hello world"])

    assert result == [[1.0, 0.0, 0.0]]


def test_embed_texts_normalizes_non_unit_vectors():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"embeddings": [{"values": [3.0, 4.0]}]}

    with patch(f"{MODULE}.settings") as settings_mock, patch(f"{MODULE}.httpx.Client") as client_cls_mock:
        settings_mock.google_api_key_embedding = "token"
        settings_mock.embedding_model = "gemini-embedding-2"
        client_instance = client_cls_mock.return_value.__enter__.return_value
        client_instance.post.return_value = fake_response

        result = embed_texts(["hello"])

    # 3-4-5 triangle: norm is 5, so [3, 4] normalizes to [0.6, 0.8]
    assert result == [[0.6, 0.8]]


def test_embed_texts_sends_batch_request_shape():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "embeddings": [{"values": [1.0, 0.0]}, {"values": [0.0, 1.0]}]
    }

    with patch(f"{MODULE}.settings") as settings_mock, patch(f"{MODULE}.httpx.Client") as client_cls_mock:
        settings_mock.google_api_key_embedding = "token"
        settings_mock.embedding_model = "gemini-embedding-2"
        client_instance = client_cls_mock.return_value.__enter__.return_value
        client_instance.post.return_value = fake_response

        result = embed_texts(["one", "two"])

    assert result == [[1.0, 0.0], [0.0, 1.0]]
    call_kwargs = client_instance.post.call_args.kwargs
    assert call_kwargs["headers"] == {"x-goog-api-key": "token"}
    assert call_kwargs["json"]["requests"] == [
        {
            "model": "models/gemini-embedding-2",
            "content": {"parts": [{"text": "one"}]},
            "outputDimensionality": 1024,
        },
        {
            "model": "models/gemini-embedding-2",
            "content": {"parts": [{"text": "two"}]},
            "outputDimensionality": 1024,
        },
    ]


def test_embed_texts_raises_when_key_missing():
    with patch(f"{MODULE}.settings") as settings_mock:
        settings_mock.google_api_key_embedding = None
        try:
            embed_texts(["hello"])
            assert False, "expected AppError"
        except AppError as exc:
            assert exc.error_code == "EMBEDDING_FAILED"


def test_embed_texts_raises_on_malformed_response():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"embeddings": []}

    with patch(f"{MODULE}.settings") as settings_mock, patch(f"{MODULE}.httpx.Client") as client_cls_mock:
        settings_mock.google_api_key_embedding = "token"
        settings_mock.embedding_model = "gemini-embedding-2"
        client_instance = client_cls_mock.return_value.__enter__.return_value
        client_instance.post.return_value = fake_response

        try:
            embed_texts(["hello"])
            assert False, "expected AppError"
        except AppError as exc:
            assert exc.error_code == "EMBEDDING_FAILED"


def test_embed_text_returns_single_vector():
    with patch(f"{MODULE}.embed_texts", return_value=[[0.4, 0.5]]) as embed_texts_mock:
        result = embed_text("a query")

    embed_texts_mock.assert_called_once_with(["a query"])
    assert result == [0.4, 0.5]


def test_embed_text_returns_empty_list_when_no_vectors():
    with patch(f"{MODULE}.embed_texts", return_value=[]):
        assert embed_text("anything") == []


def test_embed_chunks_calls_google_ai_and_returns_embedded_chunks():
    scan_id = uuid4()
    file_id = uuid4()
    chunk_id = str(uuid4())
    chunk = CodeChunk(
        scan_id=scan_id,
        file_id=file_id,
        symbol_id=None,
        chunk_type="function_chunk",
        language="python",
        file_path="app/main.py",
        symbol_name="handler",
        start_line=1,
        end_line=5,
        content="def handler(): pass",
        content_hash="abc123",
        token_count=4,
    )

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"embeddings": [{"values": [1.0, 0.0]}]}

    with patch(f"{MODULE}.settings") as settings_mock, patch(f"{MODULE}.httpx.Client") as client_cls_mock:
        settings_mock.google_api_key_embedding = "token"
        settings_mock.embedding_model = "gemini-embedding-2"
        client_instance = client_cls_mock.return_value.__enter__.return_value
        client_instance.post.return_value = fake_response

        result = embed_chunks([chunk], [chunk_id])

    assert len(result) == 1
    assert isinstance(result[0], EmbeddedChunk)
    assert str(result[0].chunk_id) == chunk_id
    assert result[0].vector == [1.0, 0.0]
    assert result[0].payload["file_path"] == "app/main.py"


def test_embed_chunks_returns_empty_list_for_no_chunks():
    assert embed_chunks([], []) == []
