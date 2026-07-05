from app.core.config import Settings, get_settings


def test_default_settings_load():
    settings = Settings(_env_file=None)
    assert settings.APP_NAME == "TalentFlow AI"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.EMBEDDING_DIM == 1536


def test_cors_origins_split_from_csv_string():
    settings = Settings(_env_file=None, CORS_ORIGINS="http://a.com, http://b.com")
    assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com"]


def test_cors_origins_accepts_list_directly():
    settings = Settings(_env_file=None, CORS_ORIGINS=["http://a.com"])
    assert settings.CORS_ORIGINS == ["http://a.com"]


def test_cors_origins_parses_from_real_env_var_not_just_kwarg():
    """
    Regression test: pydantic-settings attempts to JSON-decode any
    List[str]-typed field sourced from an environment variable BEFORE
    field_validator runs. A plain comma-separated string like
    "http://a.com,http://b.com" is not valid JSON, so without NoDecode this
    crashes at Settings() construction — exactly what happened trying to
    start the server with CORS_ORIGINS=http://localhost:3000 in .env.
    """
    import os

    os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:3001"
    try:
        settings = Settings(_env_file=None)
        assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:3001"]
    finally:
        del os.environ["CORS_ORIGINS"]


def test_env_example_placeholders_are_not_truthy_secrets():
    """
    The README instructs `cp .env.example .env`. If .env.example ships a
    non-empty placeholder for a secret (e.g. "sk-..."), a fresh copy would
    make get_settings() believe a real key is configured, silently switching
    behavior (e.g. OpenAIEmbeddingClient instead of FakeEmbeddingClient) and
    breaking anyone who follows the setup instructions literally.
    """
    import pathlib

    env_example_path = pathlib.Path(__file__).parent.parent / ".env.example"
    content = env_example_path.read_text()

    for line in content.splitlines():
        if line.startswith("OPENAI_API_KEY=") or line.startswith("ENKRYPT_API_KEY="):
            _, _, value = line.partition("=")
            assert value.strip() == "", f"'{line}' must be empty in .env.example, not a placeholder value"


def test_get_settings_is_cached():
    a = get_settings()
    b = get_settings()
    assert a is b


def test_environment_literal_rejects_invalid_value():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT="not_a_real_env")
