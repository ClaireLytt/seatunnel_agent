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
        stored = json.loads(raw)["active"]["API_KEY"]
        assert stored.startswith(("enc1:", "obf1:"))

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
        assert settings_store.mask_secret("sk-9chars") == "***"   # <12: all hidden
        assert settings_store.mask_secret("sk-abcdefgh1234") == "sk-***1234"


class TestProfiles:
    def test_roundtrip_and_activate(self, store, monkeypatch):
        settings_store.save_profile("kimi", {
            "LLM_PROVIDER": "openai", "API_KEY": "sk-kimi-1234567890",
            "MODEL_NAME": "kimi-k2"})
        settings_store.save_profile("claude", {"MODEL_NAME": "claude-opus-5"})
        assert settings_store.list_profiles() == ["claude", "kimi"]
        # saving a profile does not touch the active overrides
        assert not settings_store.has_saved()
        settings_store.activate_profile("kimi")
        assert os.environ["MODEL_NAME"] == "kimi-k2"
        assert settings_store.load_saved()["API_KEY"] == "sk-kimi-1234567890"

    def test_profile_secret_encrypted_at_rest(self, store):
        settings_store.save_profile("p", {"API_KEY": "sk-profile-secret-77"})
        assert "sk-profile-secret-77" not in store.read_text(encoding="utf-8")

    def test_clear_keeps_profiles(self, store):
        settings_store.save_profile("p", {"MODEL_NAME": "m"})
        settings_store.activate_profile("p")
        settings_store.clear()
        assert not settings_store.has_saved()
        assert settings_store.list_profiles() == ["p"]

    def test_delete_profile(self, store):
        settings_store.save_profile("p", {"MODEL_NAME": "m"})
        settings_store.delete_profile("p")
        assert settings_store.list_profiles() == []
        assert not store.exists()          # empty store file removed

    def test_activate_missing_raises(self, store):
        with pytest.raises(KeyError):
            settings_store.activate_profile("nope")

    def test_name_required_and_cap(self, store):
        with pytest.raises(ValueError):
            settings_store.save_profile("  ", {"MODEL_NAME": "m"})
        for i in range(settings_store._MAX_PROFILES):
            settings_store.save_profile(f"p{i}", {"MODEL_NAME": "m"})
        with pytest.raises(ValueError):
            settings_store.save_profile("overflow", {"MODEL_NAME": "m"})

    def test_legacy_v1_file_reads_as_active(self, store):
        store.write_text(json.dumps({"MODEL_NAME": "legacy-m"}),
                         encoding="utf-8")
        assert settings_store.load_saved() == {"MODEL_NAME": "legacy-m"}
        assert settings_store.list_profiles() == []


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
