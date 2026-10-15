"""Auth gate for non-loopback / --share UI launches (launch_app)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from seatunnel_agent.hub.ui import _resolve_ui_auth, launch_app


def test_loopback_without_auth_launches(monkeypatch):
    monkeypatch.delenv("SEATUNNEL_UI_AUTH", raising=False)
    assert _resolve_ui_auth("127.0.0.1", share=False, insecure=False) is None
    assert _resolve_ui_auth("localhost", share=False, insecure=False) is None


def test_nonloopback_without_auth_refuses(monkeypatch):
    monkeypatch.delenv("SEATUNNEL_UI_AUTH", raising=False)
    with pytest.raises(SystemExit, match="SEATUNNEL_UI_AUTH"):
        _resolve_ui_auth("0.0.0.0", share=False, insecure=False)
    # --share exposes the UI even on a loopback host
    with pytest.raises(SystemExit, match="SEATUNNEL_UI_AUTH"):
        _resolve_ui_auth("127.0.0.1", share=True, insecure=False)


def test_nonloopback_with_env_auth_launches(monkeypatch):
    monkeypatch.setenv("SEATUNNEL_UI_AUTH", "admin:secret")
    assert _resolve_ui_auth("0.0.0.0", share=False, insecure=False) == ("admin", "secret")


def test_malformed_env_auth_refuses(monkeypatch):
    monkeypatch.setenv("SEATUNNEL_UI_AUTH", "no-colon")
    with pytest.raises(SystemExit, match="user:pass"):
        _resolve_ui_auth("0.0.0.0", share=False, insecure=False)


def test_nonloopback_insecure_launches_with_warning(monkeypatch, capsys):
    monkeypatch.delenv("SEATUNNEL_UI_AUTH", raising=False)
    assert _resolve_ui_auth("0.0.0.0", share=False, insecure=True) is None
    assert "WARNING" in capsys.readouterr().out


def _launch(monkeypatch, **kwargs):
    """Call launch_app with a mocked Blocks (no real server)."""
    monkeypatch.setattr("seatunnel_agent.hub.ui._port_has_listener", lambda port: False)
    app = MagicMock()
    launch_app(app, port=7999, api=False, **kwargs)
    return app


def test_launch_app_loopback_passes_no_auth(monkeypatch):
    monkeypatch.delenv("SEATUNNEL_UI_AUTH", raising=False)
    app = _launch(monkeypatch, host="127.0.0.1", share=False)
    assert app.launch.call_args.kwargs["auth"] is None
    app.block_thread.assert_called_once()


def test_launch_app_nonloopback_refuses_before_launch(monkeypatch):
    monkeypatch.delenv("SEATUNNEL_UI_AUTH", raising=False)
    monkeypatch.setattr("seatunnel_agent.hub.ui._port_has_listener", lambda port: False)
    app = MagicMock()
    with pytest.raises(SystemExit):
        launch_app(app, port=7999, host="0.0.0.0")
    app.launch.assert_not_called()


def test_launch_app_nonloopback_with_auth_passes_credentials(monkeypatch):
    monkeypatch.setenv("SEATUNNEL_UI_AUTH", "admin:secret")
    app = _launch(monkeypatch, host="0.0.0.0", share=False)
    assert app.launch.call_args.kwargs["auth"] == ("admin", "secret")


def test_launch_app_insecure_launches_without_auth(monkeypatch, capsys):
    monkeypatch.delenv("SEATUNNEL_UI_AUTH", raising=False)
    app = _launch(monkeypatch, host="0.0.0.0", insecure=True)
    assert app.launch.call_args.kwargs["auth"] is None
    assert "WARNING" in capsys.readouterr().out
