"""App-under-test subprocess management.

Launches the Gradio app on a dedicated port (default 7912, never 7860 —
that's the developer's live session) with the seeded SQLite demo database.
Guarantees the child process is killed on exit, including Ctrl+C and crashes
on Windows (``taskkill /T /F`` fallback).
"""

from __future__ import annotations

import atexit
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .seed_sqlite import DEFAULT_DB, seed_sqlite

_log = logging.getLogger(__name__)

DEFAULT_PORT = 7912
_FORBIDDEN_PORT = 7860

# Runs create_ui + launch directly instead of ui.main() — no inbrowser,
# no port-kill logic, quiet.
_LAUNCH_SNIPPET = """
import seatunnel_agent.ui as ui
app = ui.create_ui()
app.launch(server_name="127.0.0.1", server_port=%d, inbrowser=False,
           share=False, css=ui._CUSTOM_CSS, quiet=True,
           prevent_thread_lock=False)
"""


def _first_free_port(start: int) -> int:
    port = start
    for _ in range(50):
        if port == _FORBIDDEN_PORT:
            port += 1
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    raise RuntimeError(f"No free port found starting at {start}")


def _wait_http(url: str, timeout_s: float = 60.0, proc: subprocess.Popen | None = None) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(
                f"App-under-test exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status < 500:
                    return
        except Exception as e:  # noqa: BLE001 — retry until deadline
            last_err = e
        time.sleep(0.5)
    raise TimeoutError(f"App-under-test not ready at {url} within {timeout_s}s"
                       f" (last error: {last_err})")


class AppUnderTest:
    """Context manager owning the app subprocess.  Never touches port 7860."""

    def __init__(self, port: int = DEFAULT_PORT, db_path: str = DEFAULT_DB,
                 log_dir: str | Path = "runs", keep_app: bool = False,
                 external_url: str = ""):
        if port == _FORBIDDEN_PORT:
            raise ValueError("Port 7860 is reserved for the developer session")
        self.external_url = external_url
        self.port = port if external_url else _first_free_port(port)
        self.base_url = external_url or f"http://127.0.0.1:{self.port}"
        self.db_path = db_path
        self.keep_app = keep_app
        self.log_path = Path(log_dir) / "app_under_test.log"
        self.proc: subprocess.Popen | None = None
        self._log_file = None

    def __enter__(self) -> "AppUnderTest":
        seed_sqlite(self.db_path)
        if self.external_url:
            _wait_http(self.base_url, timeout_s=10)
            return self
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(self.log_path, "w", encoding="utf-8")
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        # Isolate the app-under-test from the developer's real UI-saved LLM
        # settings: /settings cases write to this run's directory instead.
        child_env = os.environ.copy()
        child_env["SEATUNNEL_LLM_SETTINGS_PATH"] = str(
            self.log_path.parent / "llm_settings.json")
        child_env["SEATUNNEL_DC_PRESETS_PATH"] = str(
            self.log_path.parent / "dc_connections.json")
        self.proc = subprocess.Popen(
            [sys.executable, "-c", _LAUNCH_SNIPPET % self.port],
            stdout=self._log_file, stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()), env=child_env, **kwargs,
        )
        atexit.register(self._kill)
        try:
            _wait_http(self.base_url, timeout_s=60, proc=self.proc)
        except Exception:
            self._kill()
            raise
        return self

    def __exit__(self, *exc) -> None:
        if not self.keep_app:
            self._kill()

    def _kill(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None or proc.poll() is not None:
            self._close_log()
            return
        try:
            if sys.platform == "win32":
                # terminate() alone can leave gradio worker children behind
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, timeout=15)
            else:
                proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            _log.warning("Failed to kill app-under-test pid=%s", proc.pid,
                         exc_info=True)
        finally:
            self._close_log()

    def _close_log(self) -> None:
        if self._log_file is not None:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

    def log_tail(self, lines: int = 200) -> str:
        """Last *lines* of the app's stdout/stderr (for failure diagnosis)."""
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(text.splitlines()[-lines:])
