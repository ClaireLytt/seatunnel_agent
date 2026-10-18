"""Incremental frontend build: _build_frontends() skips unchanged workspaces.

Tests go through the single seam _build_frontends(frontend=..., force=...):
a fake frontend/ tree is laid out in tmp_path and the npm subprocess call is
monkeypatched, so no real npm ever runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.cli_cmds.core import _build_frontends

WORKSPACES = ["shared", "alpha", "beta"]
BUILDABLE = ["alpha", "beta"]


def make_frontend(root: Path) -> Path:
    frontend = root / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text(
        json.dumps({"name": "fake-frontend", "workspaces": WORKSPACES})
    )
    (frontend / "node_modules").mkdir()
    # shared: no build script
    shared = frontend / "shared"
    (shared / "src").mkdir(parents=True)
    (shared / "package.json").write_text(json.dumps({"name": "@fake/shared"}))
    (shared / "src" / "util.ts").write_text("export const x = 1;\n")
    for name in BUILDABLE:
        ws = frontend / name
        (ws / "src").mkdir(parents=True)
        (ws / "package.json").write_text(
            json.dumps({"name": name, "scripts": {"build": "vite build"}})
        )
        (ws / "vite.config.ts").write_text("export default {};\n")
        (ws / "tsconfig.json").write_text("{}\n")
        (ws / "src" / "main.tsx").write_text(f"// {name} entry\n")
    return frontend


@pytest.fixture()
def frontend(tmp_path: Path) -> Path:
    return make_frontend(tmp_path)


@pytest.fixture()
def built(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record which workspaces npm is asked to build; never run real npm."""
    calls: list[str] = []

    def fake_run(cmd: list[str], **kwargs: object) -> object:
        assert cmd[0] == "npm"
        if "install" in cmd:
            calls.append("<install>")
        else:
            assert cmd[1:3] == ["run", "build"]
            calls.append(cmd[cmd.index("--workspace") + 1])

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("shutil.which", lambda name: "npm")
    return calls


def test_first_build_builds_all_and_writes_hash(frontend: Path, built: list[str]) -> None:
    _build_frontends(frontend=frontend)
    assert built == BUILDABLE
    for name in BUILDABLE:
        assert (frontend / name / "dist" / ".build-hash").is_file()


def test_second_run_with_no_changes_skips_all(frontend: Path, built: list[str]) -> None:
    _build_frontends(frontend=frontend)
    built.clear()
    _build_frontends(frontend=frontend)
    assert built == []


def test_changing_one_workspace_rebuilds_only_it(frontend: Path, built: list[str]) -> None:
    _build_frontends(frontend=frontend)
    built.clear()
    (frontend / "beta" / "src" / "main.tsx").write_text("// changed\n")
    _build_frontends(frontend=frontend)
    assert built == ["beta"]


def test_changing_shared_rebuilds_all(frontend: Path, built: list[str]) -> None:
    _build_frontends(frontend=frontend)
    built.clear()
    (frontend / "shared" / "src" / "util.ts").write_text("export const x = 2;\n")
    _build_frontends(frontend=frontend)
    assert built == BUILDABLE


def test_missing_dist_or_hash_rebuilds(frontend: Path, built: list[str]) -> None:
    _build_frontends(frontend=frontend)
    built.clear()
    import shutil as _shutil

    _shutil.rmtree(frontend / "alpha" / "dist")
    (frontend / "beta" / "dist" / ".build-hash").unlink()
    _build_frontends(frontend=frontend)
    assert built == BUILDABLE


def test_force_rebuilds_all(frontend: Path, built: list[str]) -> None:
    _build_frontends(frontend=frontend)
    built.clear()
    _build_frontends(frontend=frontend, force=True)
    assert built == BUILDABLE


def test_missing_node_modules_triggers_install(frontend: Path, built: list[str]) -> None:
    (frontend / "node_modules").rmdir()
    _build_frontends(frontend=frontend)
    assert built[0] == "<install>"
    assert built[1:] == BUILDABLE


class TestUiBuildForceFlag:
    """`ui --build [--force]` passes force through to _build_frontends."""

    def _invoke(self, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> object:
        import sys
        import types

        from click.testing import CliRunner

        from seatunnel_agent.cli import cli

        forced: list[bool] = []
        monkeypatch.setattr(
            "seatunnel_agent.cli_cmds.core._build_frontends",
            lambda force=False: forced.append(force),
        )
        fake_ui = types.ModuleType("seatunnel_agent.hub.ui")
        fake_ui.create_ui = lambda: object()  # type: ignore[attr-defined]
        fake_ui.launch_app = lambda *a, **k: None  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "seatunnel_agent.hub.ui", fake_ui)

        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0, result.output
        return forced

    def test_force_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._invoke(monkeypatch, ["ui", "--build", "--force"]) == [True]

    def test_default_is_not_forced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._invoke(monkeypatch, ["ui", "--build"]) == [False]
