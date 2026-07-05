import pytest

from app.schemas.evaluation import FairnessCheckResult, GroundingCheckResult
from app.services.enkrypt_client import EnkryptAIClient, EnkryptError, FakeEnkryptClient


def test_fake_client_defaults_to_passing():
    client = FakeEnkryptClient()
    fairness = client.check_fairness("some text")
    grounding = client.check_grounding("claim", "source")
    assert fairness.passed is True
    assert grounding.passed is True


def test_fake_client_fairness_can_be_overridden():
    def responder(text, context):
        return FairnessCheckResult(fairness_score=0.2, bias_flags=["age_bias"], passed=False)

    client = FakeEnkryptClient(fairness_responder=responder)
    result = client.check_fairness("some biased-sounding text")
    assert result.passed is False
    assert "age_bias" in result.bias_flags


def test_fake_client_grounding_can_be_overridden():
    def responder(claim, source):
        return GroundingCheckResult(grounding_score=0.1, ungrounded_claims=["invented achievement"], passed=False)

    client = FakeEnkryptClient(grounding_responder=responder)
    result = client.check_grounding("claim text", "source text")
    assert result.passed is False
    assert "invented achievement" in result.ungrounded_claims


def test_fake_client_logs_calls():
    client = FakeEnkryptClient()
    client.check_fairness("text1")
    client.check_grounding("claim1", "source1")
    assert client.fairness_calls == [("text1", None)]
    assert client.grounding_calls == [("claim1", "source1")]


def test_real_client_raises_without_credentials():
    with pytest.raises(EnkryptError):
        EnkryptAIClient(api_key=None, base_url=None)
