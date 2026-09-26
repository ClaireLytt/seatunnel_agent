"""Tests for settings_store (UI-saved LLM settings) and settings_ui helpers."""

from __future__ import annotations

import json
import os

import pytest

from seatunnel_agent import settings_store
from seatunnel_agent.settings_ui import _map_error, _validate


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Isolated store + encryption key + clean env + reset module state."""
    from seatunnel_agent.data_comparison import presets as presets_mod
    monkeypatch.setattr(presets_mod, "_KEY_PATH", tmp_path / "dc_secret.key")
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    path = tmp_path / "llm_settings.json"
    monkeypatch.setenv("SEATUNNEL_LLM_SETTINGS_PATH", str(path))
    for key in settings_store.MANAGED_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings_store, "_env_snapshot", None)
    yield path
    presets_mod._cached_key = None


class TestStore:
    def test_load_saved_empty(self, store):
        assert settings_store.load_saved() == {}
        assert not settings_store.has_saved()

    def test_save_roundtrip(self, store):
        settings_store.save({
            "LLM_PROVIDER": "openai",
            "API_KEY": "sk-test-1234567890",
            "MODEL_NAME": "deepseek-chat",
            "LLM_BASE_URL": "https://api.deepseek.com",
        })
        saved = settings_store.load_saved()
        assert saved["LLM_PROVIDER"] == "openai"
        assert saved["API_KEY"] == "sk-test-1234567890"
        assert saved["MODEL_NAME"] == "deepseek-chat"
        assert settings_store.has_saved()

    def test_api_key_encrypted_at_rest(self, store):
        settings_store.save({"API_KEY": "sk-plaintext-secret-999"})
        raw = store.read_text(encoding="utf-8")
        assert "sk-plaintext-secret-999" not in raw
        assert json.loads(raw)["API_KEY"].startswith(("enc1:", "obf1:"))

    def test_blank_values_dropped(self, store):
        settings_store.save({"MODEL_NAME": "m1", "LLM_BASE_URL": "  ",
                             "TEMPERATURE": ""})
        saved = settings_store.load_saved()
        assert saved == {"MODEL_NAME": "m1"}

    def test_unknown_keys_ignored(self, store):
        store.write_text(json.dumps({"MODEL_NAME": "m1", "EVIL": "x"}),
                         encoding="utf-8")
        assert settings_store.load_saved() == {"MODEL_NAME": "m1"}

    def test_corrupt_file_is_empty(self, store):
        store.write_text("{not json", encoding="utf-8")
        assert settings_store.load_saved() == {}

    def test_save_applies_to_env(self, store):
        settings_store.save({"MODEL_NAME": "override-model",
                             "API_KEY": "sk-abc-123456"})
        assert os.environ["MODEL_NAME"] == "override-model"
        assert os.environ["API_KEY"] == "sk-abc-123456"

    def test_saved_overrides_beat_prior_env(self, store, monkeypatch):
        monkeypatch.setenv("MODEL_NAME", "from-env")
        settings_store.save({"MODEL_NAME": "from-ui"})
        assert os.environ["MODEL_NAME"] == "from-ui"

    def test_clear_restores_snapshot(self, store, monkeypatch):
        monkeypatch.setenv("MODEL_NAME", "from-env")
        settings_store.save({"MODEL_NAME": "from-ui", "API_KEY": "sk-xyz-123456"})
        settings_store.clear()
        assert os.environ["MODEL_NAME"] == "from-env"   # restored
        assert "API_KEY" not in os.environ              # was absent before
        assert not settings_store.has_saved()
        assert not store.exists()

    def test_resave_narrower_set_restores_removed_key(self, store, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "https://env.example")
        settings_store.save({"LLM_BASE_URL": "https://ui.example",
                             "MODEL_NAME": "m1"})
        settings_store.save({"MODEL_NAME": "m2"})       # base URL override gone
        assert os.environ["LLM_BASE_URL"] == "https://env.example"
        assert os.environ["MODEL_NAME"] == "m2"

    def test_version_bumps(self, store):
        v0 = settings_store.get_version()
        settings_store.save({"MODEL_NAME": "m1"})
        v1 = settings_store.get_version()
        settings_store.clear()
        v2 = settings_store.get_version()
        assert v0 < v1 < v2

    def test_mask_secret(self, store):
        assert settings_store.mask_secret("") == ""
        assert settings_store.mask_secret("short") == "***"
        assert settings_store.mask_secret("sk-abcdefgh1234") == "sk-***1234"


class TestValidate:
    def test_ok(self):
        assert _validate("https://x.com", "0.5", "1000", "60", "en") is None
        assert _validate("", "", "", "", "zh") is None

    def test_bad_base_url(self):
        assert "http" in _validate("ftp://x", "", "", "", "en")

    def test_bad_temperature(self):
        assert _validate("", "abc", "", "", "en")
        assert _validate("", "3.5", "", "", "en")

    def test_bad_ints(self):
        assert _validate("", "", "-5", "", "en")
        assert _validate("", "", "", "zero", "en")


class TestMapError:
    def test_auth(self):
        err = _map_error(RuntimeError("401 authentication_error"), "sk-k", "en")
        assert "API Key" in err

    def test_connection(self):
        err = _map_error(RuntimeError("Connection refused"), "", "zh")
        assert "无法连接" in err

    def test_key_redacted(self):
        err = _map_error(RuntimeError("bad key sk-verysecret999x"),
                         "sk-verysecret999x", "en")
        assert "sk-verysecret999x" not in err
