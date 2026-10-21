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
def npm_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record which workspaces npm is asked to build; never run real npm."""
    calls: list[str] = []

    def fake_run(cmd: list[str], **kwargs: object) -> object:
        assert cmd[0] == "npm"
        if "install" in cmd:
            calls.append("<install>")
        else:
            assert cmd[1:3] == ["run", "build"]
            name = cmd[cmd.index("--workspace") + 1]
            calls.append(name)
            # a real build produces dist/
            (Path(str(kwargs["cwd"])) / name / "dist").mkdir(
                parents=True, exist_ok=True
            )

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("shutil.which", lambda name: "npm")
    return calls


def test_first_build_builds_all_and_writes_hash(frontend: Path, npm_calls: list[str]) -> None:
    _build_frontends(frontend=frontend)
    assert npm_calls == BUILDABLE
    for name in BUILDABLE:
        assert (frontend / name / "dist" / ".build-hash").is_file()


def test_second_run_with_no_changes_skips_all(frontend: Path, npm_calls: list[str]) -> None:
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    _build_frontends(frontend=frontend)
    assert npm_calls == []


def test_changing_one_workspace_rebuilds_only_it(frontend: Path, npm_calls: list[str]) -> None:
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    (frontend / "beta" / "src" / "main.tsx").write_text("// changed\n")
    _build_frontends(frontend=frontend)
    assert npm_calls == ["beta"]


def test_changing_shared_rebuilds_all(frontend: Path, npm_calls: list[str]) -> None:
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    (frontend / "shared" / "src" / "util.ts").write_text("export const x = 2;\n")
    _build_frontends(frontend=frontend)
    assert npm_calls == BUILDABLE


def test_missing_dist_or_hash_rebuilds(frontend: Path, npm_calls: list[str]) -> None:
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    import shutil as _shutil

    _shutil.rmtree(frontend / "alpha" / "dist")
    (frontend / "beta" / "dist" / ".build-hash").unlink()
    _build_frontends(frontend=frontend)
    assert npm_calls == BUILDABLE


def test_renaming_same_content_file_rebuilds(frontend: Path, npm_calls: list[str]) -> None:
    """Moving/renaming a file without changing its content must change the hash."""
    src = frontend / "alpha" / "src"
    (src / "a").mkdir()
    (src / "b").mkdir()
    (src / "a" / "mod.ts").write_text("export const same = 1;\n")
    (src / "b" / "mod.ts").write_text("export const same = 1;\n")
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    # swap the two identical files between directories (content set unchanged)
    (src / "a" / "mod.ts").rename(src / "a" / "tmp.ts")
    (src / "b" / "mod.ts").rename(src / "a" / "mod.ts")
    (src / "a" / "tmp.ts").rename(src / "b" / "mod.ts")
    _build_frontends(frontend=frontend)
    assert npm_calls == []  # same paths + same contents: no rebuild
    (src / "a" / "mod.ts").rename(src / "b" / "renamed.ts")
    _build_frontends(frontend=frontend)
    assert npm_calls == ["alpha"]


def test_build_without_dist_skips_hash_and_rebuilds(
    frontend: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If npm run build produces no dist/, no hash is written; next run rebuilds."""
    calls: list[str] = []

    def fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd[cmd.index("--workspace") + 1])

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("shutil.which", lambda name: "npm")
    _build_frontends(frontend=frontend)
    assert calls == BUILDABLE
    for name in BUILDABLE:
        assert not (frontend / name / "dist").exists()
    calls.clear()
    _build_frontends(frontend=frontend)
    assert calls == BUILDABLE


def test_shared_generated_outputs_excluded_from_hash(
    frontend: Path, npm_calls: list[str]
) -> None:
    """dist/ and *.tsbuildinfo under shared/ must not affect the hash."""
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    shared = frontend / "shared"
    (shared / "dist").mkdir()
    (shared / "dist" / "out.js").write_text("generated\n")
    (shared / "tsconfig.tsbuildinfo").write_text("{}\n")
    _build_frontends(frontend=frontend)
    assert npm_calls == []


def test_force_rebuilds_all(frontend: Path, npm_calls: list[str]) -> None:
    _build_frontends(frontend=frontend)
    npm_calls.clear()
    _build_frontends(frontend=frontend, force=True)
    assert npm_calls == BUILDABLE


def test_missing_node_modules_triggers_install(frontend: Path, npm_calls: list[str]) -> None:
    (frontend / "node_modules").rmdir()
    _build_frontends(frontend=frontend)
    assert npm_calls[0] == "<install>"
    assert npm_calls[1:] == BUILDABLE


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
            lambda force=False, jobs=None: forced.append(force),
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

    def test_force_without_build_warns_and_skips_build(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys
        import types

        from click.testing import CliRunner

        from seatunnel_agent.cli import cli

        forced: list[bool] = []
        monkeypatch.setattr(
            "seatunnel_agent.cli_cmds.core._build_frontends",
            lambda force=False, jobs=None: forced.append(force),
        )
        fake_ui = types.ModuleType("seatunnel_agent.hub.ui")
        fake_ui.create_ui = lambda: object()  # type: ignore[attr-defined]
        fake_ui.launch_app = lambda *a, **k: None  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "seatunnel_agent.hub.ui", fake_ui)

        result = CliRunner().invoke(cli, ["ui", "--force"])
        assert result.exit_code == 0, result.output
        assert forced == []
        assert "--force has no effect without --build" in result.output


def add_workspace(frontend: Path, name: str) -> None:
    """Extend the fake frontend tree with one more buildable workspace."""
    pkg = json.loads((frontend / "package.json").read_text())
    pkg["workspaces"].append(name)
    (frontend / "package.json").write_text(json.dumps(pkg))
    ws = frontend / name
    (ws / "src").mkdir(parents=True)
    (ws / "package.json").write_text(
        json.dumps({"name": name, "scripts": {"build": "vite build"}})
    )
    (ws / "vite.config.ts").write_text("export default {};\n")
    (ws / "tsconfig.json").write_text("{}\n")
    (ws / "src" / "main.tsx").write_text(f"// {name} entry\n")


class TestParallelBuild:
    """_build_frontends(jobs=N) runs pending builds in a bounded pool."""

    def _tracking_npm(
        self, monkeypatch: pytest.MonkeyPatch, fail: set[str] | None = None
    ) -> dict:
        """Fake npm that records calls and tracks peak concurrency."""
        import threading
        import time

        state: dict = {"calls": [], "current": 0, "peak": 0}
        lock = threading.Lock()

        def fake_run(cmd: list[str], **kwargs: object) -> object:
            assert cmd[0] == "npm"
            name = cmd[cmd.index("--workspace") + 1]
            with lock:
                state["calls"].append(name)
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            time.sleep(0.05)
            with lock:
                state["current"] -= 1
            rc = 1 if fail and name in fail else 0
            if rc == 0:
                (Path(str(kwargs["cwd"])) / name / "dist").mkdir(
                    parents=True, exist_ok=True
                )

            class R:
                returncode = rc
                stdout = f"{name} build output\n"
                stderr = ""

            return R()

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("shutil.which", lambda name: "npm")
        return state

    def test_parallel_builds_all_within_jobs_limit(
        self, frontend: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in ("gamma", "delta"):
            add_workspace(frontend, name)
        state = self._tracking_npm(monkeypatch)
        _build_frontends(frontend=frontend, jobs=2)
        assert sorted(state["calls"]) == sorted(BUILDABLE + ["gamma", "delta"])
        assert state["peak"] <= 2
        assert state["peak"] >= 2  # actually ran in parallel
        for name in BUILDABLE + ["gamma", "delta"]:
            assert (frontend / name / "dist" / ".build-hash").is_file()

    def test_unchanged_workspaces_skip_pool(
        self, frontend: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = self._tracking_npm(monkeypatch)
        _build_frontends(frontend=frontend, jobs=4)
        state["calls"].clear()
        _build_frontends(frontend=frontend, jobs=4)
        assert state["calls"] == []
        out = capsys.readouterr().out
        for name in BUILDABLE:
            assert f"{name}: skipped (unchanged)" in out

    def test_failure_finishes_others_and_lists_all_failed(
        self, frontend: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        add_workspace(frontend, "gamma")
        state = self._tracking_npm(monkeypatch, fail={"alpha", "gamma"})
        with pytest.raises(SystemExit) as exc:
            _build_frontends(frontend=frontend, jobs=2)
        assert exc.value.code != 0
        assert sorted(state["calls"]) == sorted(BUILDABLE + ["gamma"])
        out = capsys.readouterr().out
        assert "alpha" in out and "gamma" in out
        assert not (frontend / "alpha" / "dist" / ".build-hash").exists()
        assert not (frontend / "gamma" / "dist" / ".build-hash").exists()
        assert (frontend / "beta" / "dist" / ".build-hash").is_file()

    def test_failed_workspace_rebuilds_next_time(
        self, frontend: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._tracking_npm(monkeypatch, fail={"alpha"})
        with pytest.raises(SystemExit):
            _build_frontends(frontend=frontend, jobs=2)
        state2 = self._tracking_npm(monkeypatch)
        _build_frontends(frontend=frontend, jobs=2)
        assert state2["calls"] == ["alpha"]

    def test_output_flushed_as_prefixed_block(
        self, frontend: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._tracking_npm(monkeypatch)
        _build_frontends(frontend=frontend, jobs=2)
        out = capsys.readouterr().out
        for name in BUILDABLE:
            assert f"[{name}] {name} build output" in out

    def test_jobs_1_equivalent_to_sequential(
        self, frontend: Path, npm_calls: list[str]
    ) -> None:
        _build_frontends(frontend=frontend, jobs=1)
        assert npm_calls == BUILDABLE
        for name in BUILDABLE:
            assert (frontend / name / "dist" / ".build-hash").is_file()
        npm_calls.clear()
        _build_frontends(frontend=frontend, jobs=1)
        assert npm_calls == []


class TestUiBuildJobsFlag:
    """`ui --build --jobs N` passes jobs through to _build_frontends."""

    def _invoke(self, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> tuple:
        import sys
        import types

        from click.testing import CliRunner

        from seatunnel_agent.cli import cli

        kwargs_seen: list[dict] = []
        monkeypatch.setattr(
            "seatunnel_agent.cli_cmds.core._build_frontends",
            lambda force=False, jobs=None: kwargs_seen.append(
                {"force": force, "jobs": jobs}
            ),
        )
        fake_ui = types.ModuleType("seatunnel_agent.hub.ui")
        fake_ui.create_ui = lambda: object()  # type: ignore[attr-defined]
        fake_ui.launch_app = lambda *a, **k: None  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "seatunnel_agent.hub.ui", fake_ui)

        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0, result.output
        return kwargs_seen, result

    def test_jobs_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kwargs_seen, _ = self._invoke(monkeypatch, ["ui", "--build", "--jobs", "3"])
        assert kwargs_seen == [{"force": False, "jobs": 3}]

    def test_default_jobs_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kwargs_seen, _ = self._invoke(monkeypatch, ["ui", "--build"])
        assert kwargs_seen == [{"force": False, "jobs": None}]

    def test_jobs_without_build_warns_and_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kwargs_seen, result = self._invoke(monkeypatch, ["ui", "--jobs", "3"])
        assert kwargs_seen == []
        assert "--jobs has no effect without --build" in result.output


class TestBuildSummaryLine:
    """_build_frontends prints one summary line with counts and elapsed time."""

    def test_summary_counts_built_and_skipped(
        self, frontend: Path, npm_calls: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        _build_frontends(frontend=frontend)
        out = capsys.readouterr().out
        assert "frontend build: 2 built, 0 skipped, 0 failed in " in out
        _build_frontends(frontend=frontend)
        out = capsys.readouterr().out
        assert "frontend build: 0 built, 2 skipped, 0 failed in " in out

    def test_summary_counts_failed(
        self, frontend: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = TestParallelBuild()._tracking_npm(monkeypatch, fail={"alpha"})
        with pytest.raises(SystemExit):
            _build_frontends(frontend=frontend, jobs=2)
        assert sorted(state["calls"]) == BUILDABLE
        out = capsys.readouterr().out
        assert "frontend build: 1 built, 0 skipped, 1 failed in " in out

    def test_summary_elapsed_has_seconds_unit(
        self, frontend: Path, npm_calls: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        import re

        _build_frontends(frontend=frontend)
        out = capsys.readouterr().out
        assert re.search(r"frontend build: 2 built, 0 skipped, 0 failed in \d+\.\d+s", out)
