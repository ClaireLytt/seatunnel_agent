from __future__ import annotations

import pytest

from seatunnel_agent.config import Settings, load_settings


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
