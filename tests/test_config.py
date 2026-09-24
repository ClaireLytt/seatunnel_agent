from __future__ import annotations

import pytest

from seatunnel_agent.config import Settings, env_float, env_int, load_settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Prevent .env file from leaking real values into tests."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SEATUNNEL_HOME", raising=False)
    monkeypatch.delenv("MAX_RETRIES", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr("seatunnel_agent.config.load_dotenv", lambda: None)


def test_load_settings_missing_api_key(monkeypatch):
    monkeypatch.setenv("SEATUNNEL_HOME", "/tmp/seatunnel")
    with pytest.raises(RuntimeError, match="API_KEY"):
        load_settings()


def test_load_settings_missing_seatunnel_home_ok(monkeypatch):
    """SEATUNNEL_HOME is optional — no error when unset."""
    monkeypatch.setenv("API_KEY", "sk-test")
    settings = load_settings()
    assert settings.seatunnel_home == ""
    assert settings.seatunnel_bin == ""


def test_load_settings_defaults(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("SEATUNNEL_HOME", "/tmp/seatunnel")
    settings = load_settings()
    assert settings.api_key == "sk-test"
    assert settings.max_retries == 3
    assert settings.model_name == "claude-opus-5"


def test_load_settings_custom_values(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-custom")
    monkeypatch.setenv("SEATUNNEL_HOME", "/opt/seatunnel")
    monkeypatch.setenv("MAX_RETRIES", "5")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5")
    settings = load_settings()
    assert settings.max_retries == 5
    assert settings.model_name == "claude-sonnet-5"


def test_load_settings_backward_compat_anthropic_key(monkeypatch):
    """ANTHROPIC_API_KEY still works as fallback."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-old-key")
    monkeypatch.setenv("SEATUNNEL_HOME", "/tmp/seatunnel")
    settings = load_settings()
    assert settings.api_key == "sk-old-key"


def test_load_settings_api_key_takes_precedence(monkeypatch):
    """API_KEY is preferred over ANTHROPIC_API_KEY."""
    monkeypatch.setenv("API_KEY", "sk-new")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-old")
    monkeypatch.setenv("SEATUNNEL_HOME", "/tmp/seatunnel")
    settings = load_settings()
    assert settings.api_key == "sk-new"


def test_settings_is_frozen():
    s = Settings(api_key="k", seatunnel_home="/tmp")
    with pytest.raises(AttributeError):
        s.max_retries = 10  # type: ignore[misc]


def test_seatunnel_bin_computed(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("SEATUNNEL_HOME", "/tmp/seatunnel")
    settings = load_settings()
    assert "seatunnel" in settings.seatunnel_bin


def test_load_settings_validates_provider(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("SEATUNNEL_HOME", "/tmp/seatunnel")
    monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")
    with pytest.raises(RuntimeError, match="LLM_PROVIDER"):
        load_settings()


def test_backward_compat_property():
    """Settings.anthropic_api_key property returns api_key."""
    s = Settings(api_key="sk-test", seatunnel_home="/tmp")
    assert s.anthropic_api_key == "sk-test"


def test_load_settings_job_timeout(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("JOB_TIMEOUT", "300")
    settings = load_settings()
    assert settings.job_timeout == 300


def test_load_settings_temperature(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("TEMPERATURE", "0.7")
    settings = load_settings()
    assert settings.temperature == 0.7


def test_load_settings_config_dir(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("CONFIG_DIR", "/custom/configs")
    settings = load_settings()
    assert settings.config_dir == "/custom/configs"


def test_load_settings_max_tokens(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("MAX_TOKENS", "32000")
    settings = load_settings()
    assert settings.max_tokens == 32000


def test_load_settings_invalid_int_names_variable(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("MAX_RETRIES", "three")
    with pytest.raises(RuntimeError, match="MAX_RETRIES"):
        load_settings()


def test_load_settings_invalid_float_names_variable(monkeypatch):
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("TEMPERATURE", "hot")
    with pytest.raises(RuntimeError, match="TEMPERATURE"):
        load_settings()


def test_env_int_fallback_on_garbage(monkeypatch):
    monkeypatch.setenv("SOME_INT_VAR", "not-a-number")
    assert env_int("SOME_INT_VAR", 42) == 42


def test_env_int_reads_valid_value(monkeypatch):
    monkeypatch.setenv("SOME_INT_VAR", "7")
    assert env_int("SOME_INT_VAR", 42) == 7


def test_env_int_unset_returns_default(monkeypatch):
    monkeypatch.delenv("SOME_INT_VAR", raising=False)
    assert env_int("SOME_INT_VAR", 42) == 42


def test_env_float_fallback_on_garbage(monkeypatch):
    monkeypatch.setenv("SOME_FLOAT_VAR", "abc")
    assert env_float("SOME_FLOAT_VAR", 1.5) == 1.5


def test_env_float_reads_valid_value(monkeypatch):
    monkeypatch.setenv("SOME_FLOAT_VAR", "0.25")
    assert env_float("SOME_FLOAT_VAR", 1.5) == 0.25
