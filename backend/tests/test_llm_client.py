import pytest

from app.services.llm_client import FakeLLMClient, LLMError, OpenAILLMClient


def test_fake_client_constant_mode():
    client = FakeLLMClient.constant({"answer": 42})
    assert client.complete_json("system", "user") == {"answer": 42}
    assert client.complete_json("system", "other user") == {"answer": 42}


def test_fake_client_queue_mode_pops_in_order():
    client = FakeLLMClient(queue=[{"result": "first"}, {"result": "second"}])
    assert client.complete_json("s", "u") == {"result": "first"}
    assert client.complete_json("s", "u") == {"result": "second"}


def test_fake_client_queue_exhausted_raises():
    client = FakeLLMClient(queue=[{"result": "only"}])
    client.complete_json("s", "u")
    with pytest.raises(LLMError):
        client.complete_json("s", "u")


def test_fake_client_responder_mode_receives_prompts():
    def responder(system, user):
        return {"echoed_user": user}

    client = FakeLLMClient(responder=responder)
    result = client.complete_json("sys prompt", "hello world")
    assert result == {"echoed_user": "hello world"}


def test_fake_client_requires_exactly_one_mode():
    with pytest.raises(ValueError):
        FakeLLMClient()
    with pytest.raises(ValueError):
        FakeLLMClient(responder=lambda s, u: {}, queue=[{}])


def test_fake_client_logs_calls():
    client = FakeLLMClient.constant({})
    client.complete_json("sys", "user1")
    client.complete_json("sys", "user2")
    assert len(client.call_log) == 2
    assert client.call_log[0] == ("sys", "user1")


def test_openai_client_raises_without_api_key():
    with pytest.raises(LLMError):
        OpenAILLMClient(api_key=None)
