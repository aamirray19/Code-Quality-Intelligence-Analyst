from unittest.mock import MagicMock, patch

from app.services.embedding_service import embed_text, embed_texts

MODULE = "app.services.embedding_service"


def test_embed_texts_calls_hf_and_returns_vectors():
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = [[0.1, 0.2, 0.3]]

    with patch(f"{MODULE}.settings") as settings_mock, patch(f"{MODULE}.httpx.Client") as client_cls_mock:
        settings_mock.hf_api_token = "token"
        settings_mock.embedding_model = "Qwen/Qwen3-Embedding-0.6B"
        client_instance = client_cls_mock.return_value.__enter__.return_value
        client_instance.post.return_value = fake_response

        result = embed_texts(["hello world"])

    assert result == [[0.1, 0.2, 0.3]]


def test_embed_text_returns_single_vector():
    with patch(f"{MODULE}.embed_texts", return_value=[[0.4, 0.5]]) as embed_texts_mock:
        result = embed_text("a query")

    embed_texts_mock.assert_called_once_with(["a query"])
    assert result == [0.4, 0.5]


def test_embed_text_returns_empty_list_when_no_vectors():
    with patch(f"{MODULE}.embed_texts", return_value=[]):
        assert embed_text("anything") == []
