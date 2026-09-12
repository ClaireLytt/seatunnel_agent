from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import Settings
from .utils import safe_json, truncate

# ---------------------------------------------------------------------------
# Tool JSON schemas (sent to Claude)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "run_seatunnel_job",
        "description": (
            "Execute a SeaTunnel job using the specified config file. "
            "Returns stdout and stderr from the SeaTunnel CLI. "
            "Call this after creating or fixing a config to test if the job runs successfully."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the SeaTunnel HOCON config file",
                },
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "read_log",
        "description": (
            "Read SeaTunnel log file for error analysis. "
            "Returns the last N lines of the log. "
            "Use this when a job fails and you need to find the root cause. "
            "Pass 'auto' as log_path to automatically find the latest log in $SEATUNNEL_HOME/logs/."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {
                    "type": "string",
                    "description": "Path to the log file, or 'auto' to find the latest log",
                },
                "tail_lines": {
                    "type": "integer",
                    "description": "Number of lines to read from the end (default 100)",
                },
            },
            "required": ["log_path"],
        },
    },
    {
        "name": "read_config",
        "description": "Read the contents of a SeaTunnel HOCON config file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file to read",
                },
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "write_config",
        "description": (
            "Write or overwrite a SeaTunnel HOCON config file. "
            "Creates a .bak backup of the original if it exists. "
            "The content should be valid HOCON format with env, source, transform, and sink blocks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to write the config file",
                },
                "content": {
                    "type": "string",
                    "description": "The full HOCON config content to write",
                },
            },
            "required": ["config_path", "content"],
        },
    },
    {
        "name": "validate_config",
        "description": (
            "Validate a SeaTunnel config file for syntax errors and structural issues. "
            "Checks HOCON syntax and verifies required sections (source, sink) exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file to validate",
                },
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "list_connectors",
        "description": (
            "List available SeaTunnel connectors installed in the current SeaTunnel installation. "
            "Returns source and sink connector names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor functions
# ---------------------------------------------------------------------------


def _run_seatunnel_job(settings: Settings, config_path: str) -> str:
    if not Path(settings.seatunnel_bin).exists():
        return safe_json({
            "success": False,
            "exit_code": -1,
            "error": (
                f"SeaTunnel binary not found at {settings.seatunnel_bin}. "
                "Check that SEATUNNEL_HOME is set correctly in .env"
            ),
        })

    config = Path(config_path)
    if not config.exists():
        return safe_json({
            "success": False,
            "exit_code": -1,
            "error": f"Config file not found: {config_path}",
        })

    try:
        result = subprocess.run(
            [settings.seatunnel_bin, "--config", str(config.resolve())],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return safe_json({
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": truncate(result.stdout),
            "stderr": truncate(result.stderr),
        })
    except subprocess.TimeoutExpired:
        return safe_json({
            "success": False,
            "exit_code": -1,
            "error": "SeaTunnel job timed out after 120 seconds",
        })
    except OSError as e:
        return safe_json({
            "success": False,
            "exit_code": -1,
            "error": f"Failed to execute SeaTunnel: {e}",
        })


def _read_log(settings: Settings, log_path: str, tail_lines: int = 100) -> str:
    from .utils import resolve_log_path

    try:
        resolved = resolve_log_path(log_path, settings.seatunnel_home)
    except FileNotFoundError as e:
        return safe_json({"error": str(e)})

    try:
        lines = Path(resolved).read_text(encoding="utf-8", errors="replace").splitlines()
        tail = lines[-tail_lines:] if len(lines) > tail_lines else lines
        return safe_json({
            "log_path": resolved,
            "total_lines": len(lines),
            "returned_lines": len(tail),
            "content": "\n".join(tail),
        })
    except FileNotFoundError:
        return safe_json({"error": f"Log file not found: {resolved}"})
    except PermissionError:
        return safe_json({"error": f"Permission denied reading: {resolved}"})


def _read_config(settings: Settings, config_path: str) -> str:
    try:
        content = Path(config_path).read_text(encoding="utf-8")
        return safe_json({
            "config_path": config_path,
            "content": content,
        })
    except FileNotFoundError:
        return safe_json({"error": f"Config file not found: {config_path}"})
    except PermissionError:
        return safe_json({"error": f"Permission denied reading: {config_path}"})


def _write_config(settings: Settings, config_path: str, content: str) -> str:
    path = Path(config_path)

    if not path.suffix or path.suffix not in (".conf", ".hocon", ".config", ".json"):
        return safe_json({
            "error": (
                f"Refusing to write to {config_path} — "
                "expected a .conf, .hocon, .config, or .json file extension"
            ),
        })

    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    return safe_json({
        "success": True,
        "config_path": str(path),
        "message": f"Config written to {path}",
    })


def _validate_config(settings: Settings, config_path: str) -> str:
    path = Path(config_path)
    if not path.exists():
        return safe_json({
            "valid": False,
            "errors": [f"Config file not found: {config_path}"],
        })

    try:
        from pyhocon import ConfigFactory, ConfigException
    except ImportError:
        return safe_json({
            "valid": False,
            "errors": ["pyhocon is not installed — run: pip install pyhocon"],
        })

    errors: list[str] = []
    warnings: list[str] = []
    sections_found: list[str] = []

    try:
        config = ConfigFactory.parse_file(str(path))
    except Exception as e:
        return safe_json({
            "valid": False,
            "errors": [f"HOCON syntax error: {e}"],
            "warnings": [],
            "sections_found": [],
        })

    for section in ("env", "source", "transform", "sink"):
        try:
            config[section]
            sections_found.append(section)
        except Exception:
            pass

    if "source" not in sections_found:
        errors.append("Missing required 'source' section")
    if "sink" not in sections_found:
        errors.append("Missing required 'sink' section")
    if "env" not in sections_found:
        warnings.append("Missing 'env' section — defaults will be used")
    if "transform" not in sections_found:
        warnings.append("No 'transform' section — data passes through unchanged")

    return safe_json({
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "sections_found": sections_found,
    })


_COMMON_CONNECTORS = {
    "sources": [
        "FakeSource", "Jdbc", "MySQL-CDC", "PostgreSQL-CDC",
        "Kafka", "LocalFile", "HdfsFile", "S3File",
        "MongoDB", "HTTP", "Socket",
    ],
    "sinks": [
        "Console", "Jdbc", "Kafka", "LocalFile", "HdfsFile",
        "S3File", "Hive", "ClickHouse", "Doris",
        "Elasticsearch", "MongoDB", "StarRocks",
    ],
}


def _list_connectors(settings: Settings) -> str:
    connectors_dir = Path(settings.seatunnel_home) / "connectors"

    if not connectors_dir.is_dir():
        return safe_json({
            "note": (
                "Could not scan connectors directory. "
                "Showing common built-in connectors instead."
            ),
            **_COMMON_CONNECTORS,
        })

    jar_pattern = re.compile(r"connector-(\w[\w-]*?)-[\d.]+.*\.jar", re.IGNORECASE)
    names: set[str] = set()
    for jar in connectors_dir.glob("*.jar"):
        m = jar_pattern.match(jar.name)
        if m:
            names.add(m.group(1))

    if not names:
        return safe_json({
            "note": "No connector JARs found. Showing common connectors.",
            **_COMMON_CONNECTORS,
        })

    return safe_json({
        "installed_connectors": sorted(names),
        "count": len(names),
    })


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "run_seatunnel_job": _run_seatunnel_job,
    "read_log": _read_log,
    "read_config": _read_config,
    "write_config": _write_config,
    "validate_config": _validate_config,
    "list_connectors": _list_connectors,
}


def execute_tool(tool_name: str, tool_input: dict[str, Any], settings: Settings) -> str:
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return safe_json({"error": f"Unknown tool: {tool_name}"})
    try:
        return fn(settings, **tool_input)
    except Exception as e:
        return safe_json({"error": f"Tool '{tool_name}' failed: {e}"})
