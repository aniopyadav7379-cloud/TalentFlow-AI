import pytest

from app.services.embeddings import EmbeddingError, FakeEmbeddingClient, OpenAIEmbeddingClient


def test_fake_client_is_deterministic():
    client = FakeEmbeddingClient(dim=16)
    vec1 = client.embed_one("hello world")
    vec2 = client.embed_one("hello world")
    assert vec1 == vec2


def test_fake_client_different_text_gives_different_vector():
    client = FakeEmbeddingClient(dim=16)
    vec1 = client.embed_one("python backend engineer")
    vec2 = client.embed_one("marketing manager")
    assert vec1 != vec2


def test_fake_client_respects_configured_dimension():
    client = FakeEmbeddingClient(dim=32)
    vec = client.embed_one("some text")
    assert len(vec) == 32


def test_fake_client_embed_batch_preserves_order():
    client = FakeEmbeddingClient(dim=8)
    texts = ["first", "second", "third"]
    vectors = client.embed(texts)
    assert len(vectors) == 3
    assert vectors[0] == client.embed_one("first")
    assert vectors[2] == client.embed_one("third")


def test_fake_client_handles_empty_list():
    client = FakeEmbeddingClient(dim=8)
    assert client.embed([]) == []


def test_fake_client_values_are_normalized_range():
    client = FakeEmbeddingClient(dim=16)
    vec = client.embed_one("test text")
    assert all(-1.0 <= v <= 1.0 for v in vec)


def test_openai_client_raises_without_api_key():
    with pytest.raises(EmbeddingError):
        OpenAIEmbeddingClient(api_key=None)
