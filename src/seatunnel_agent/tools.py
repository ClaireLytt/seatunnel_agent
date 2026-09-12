from __future__ import annotations

import difflib
import json
import re
import shutil
import socket
import subprocess
import time
from datetime import datetime
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
    {
        "name": "test_connection",
        "description": (
            "Test TCP connectivity to a host:port. "
            "Use before generating configs that depend on external services "
            "(databases, Kafka, etc.) to verify the service is reachable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Hostname or IP address to test",
                },
                "port": {
                    "type": "integer",
                    "description": "Port number to test",
                },
                "service_type": {
                    "type": "string",
                    "description": "Service type for display (e.g. 'MySQL', 'Kafka'). Optional.",
                },
            },
            "required": ["host", "port"],
        },
    },
    {
        "name": "list_templates",
        "description": (
            "List available pipeline config templates. "
            "Each template has a name, description, and list of parameters. "
            "Use when the user wants a common pipeline pattern."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category: 'testing', 'database', 'streaming', 'file'. Optional.",
                },
            },
        },
    },
    {
        "name": "use_template",
        "description": (
            "Generate a SeaTunnel config from a template with specific parameter values. "
            "Call list_templates first to see available templates and their parameters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of the template to use",
                },
                "parameters": {
                    "type": "object",
                    "description": "Key-value pairs for template parameters",
                },
                "config_path": {
                    "type": "string",
                    "description": "Path to write the generated config file",
                },
            },
            "required": ["template_name", "parameters", "config_path"],
        },
    },
    {
        "name": "query_connector_docs",
        "description": (
            "Look up parameter documentation for a SeaTunnel connector. "
            "Returns required/optional parameters with types, descriptions, and examples. "
            "Use this before generating configs to ensure correct parameter names and values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "connector_name": {
                    "type": "string",
                    "description": "Name of the connector (e.g. 'Jdbc', 'Kafka', 'FakeSource')",
                },
                "param_name": {
                    "type": "string",
                    "description": "Optional: specific parameter name to get details for",
                },
            },
            "required": ["connector_name"],
        },
    },
    {
        "name": "list_config_versions",
        "description": (
            "List version history of a config file. "
            "Shows all saved versions with timestamps and sizes. "
            "Use when the user wants to see or revert config changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file to check history for",
                },
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "run_batch",
        "description": (
            "Run multiple SeaTunnel pipeline configs sequentially. "
            "Returns per-job results and a summary with total/passed/failed counts. "
            "Use when the user wants to run several configs in one go."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of config file paths to run sequentially",
                },
                "stop_on_failure": {
                    "type": "boolean",
                    "description": "Stop executing remaining configs if one fails (default: true)",
                },
            },
            "required": ["config_paths"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor functions
# ---------------------------------------------------------------------------


def _parse_job_metrics(stdout: str, stderr: str) -> dict[str, Any] | None:
    """Extract execution metrics from SeaTunnel job output."""
    metrics: dict[str, Any] = {}
    combined = stdout + "\n" + stderr

    patterns = {
        "total_read_count": [
            r"Total Read Count\s*[:=]\s*(\d+)",
            r"SourceReceivedCount\s*[:=]\s*(\d+)",
        ],
        "total_write_count": [
            r"Total Write Count\s*[:=]\s*(\d+)",
            r"SinkWriteCount\s*[:=]\s*(\d+)",
        ],
        "total_read_bytes": [r"Total Read Bytes\s*[:=]\s*(\d+)"],
        "total_write_bytes": [r"Total Write Bytes\s*[:=]\s*(\d+)"],
    }

    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, combined, re.IGNORECASE)
            if m:
                metrics[key] = int(m.group(1))
                break

    duration_match = re.search(
        r"(?:elapsed|duration|took)\s*[:=]?\s*(\d+)\s*(ms|s|seconds|milliseconds)",
        combined, re.IGNORECASE,
    )
    if duration_match:
        val = int(duration_match.group(1))
        unit = duration_match.group(2).lower()
        metrics["duration_ms"] = val if unit in ("ms", "milliseconds") else val * 1000

    if re.search(r"job.*finish|FINISHED|completed successfully", combined, re.IGNORECASE):
        metrics["status_summary"] = "FINISHED"
    elif re.search(r"FAILED|Exception|Error", combined, re.IGNORECASE):
        metrics["status_summary"] = "FAILED"

    return metrics if metrics else None


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
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        result_data: dict[str, Any] = {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": truncate(result.stdout),
            "stderr": truncate(result.stderr),
        }
        metrics = _parse_job_metrics(result.stdout, result.stderr)
        if metrics:
            result_data["metrics"] = metrics
        return safe_json(result_data)
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


def _save_config_version(config_path: Path, content: str) -> int:
    """Save a versioned copy. Returns version number."""
    try:
        rel = config_path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        rel = config_path
    safe_key = str(rel).replace("\\", "/").replace("/", "_")
    history_dir = Path(".config_history") / safe_key
    history_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(history_dir.glob("v*_*.*"))
    version = len(existing) + 1
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_file = history_dir / f"v{version}_{timestamp}{config_path.suffix}"
    version_file.write_text(content, encoding="utf-8")
    return version


def _write_config(settings: Settings, config_path: str, content: str) -> str:
    path = Path(config_path)

    if not path.suffix or path.suffix not in (".conf", ".hocon", ".config", ".json"):
        return safe_json({
            "error": (
                f"Refusing to write to {config_path} — "
                "expected a .conf, .hocon, .config, or .json file extension"
            ),
        })

    try:
        resolved = path.resolve()
        cwd = Path.cwd().resolve()
        if not resolved.is_relative_to(cwd):
            return safe_json({
                "error": (
                    f"Refusing to write to {config_path} — "
                    "path is outside the current working directory"
                ),
            })
    except (OSError, ValueError):
        return safe_json({"error": f"Invalid path: {config_path}"})

    old_content = None
    if path.exists():
        old_content = path.read_text(encoding="utf-8")
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    version = _save_config_version(path, content)

    result: dict[str, Any] = {
        "success": True,
        "config_path": str(path),
        "message": f"Config written to {path}",
        "version": version,
    }

    if old_content is not None and old_content != content:
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"{path.name}.bak",
            tofile=path.name,
        ))
        result["diff"] = "".join(diff_lines)
        result["had_changes"] = True
    elif old_content is not None:
        result["had_changes"] = False

    return safe_json(result)


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


def _test_connection(settings: Settings, host: str, port: int, service_type: str = "") -> str:
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=5)
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        sock.close()
        label = f"{service_type} at " if service_type else ""
        return safe_json({
            "reachable": True,
            "host": host,
            "port": port,
            "latency_ms": latency_ms,
            "message": f"{label}{host}:{port} is reachable ({latency_ms}ms)",
        })
    except (socket.timeout, socket.error, OSError) as e:
        return safe_json({
            "reachable": False,
            "host": host,
            "port": port,
            "error": str(e),
            "message": f"Cannot reach {host}:{port} — {e}",
        })


def _list_templates(settings: Settings, category: str = "") -> str:
    from .templates import list_templates as _lt

    templates = _lt(category or None)
    return safe_json({
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": t.parameters,
            }
            for t in templates
        ],
        "count": len(templates),
    })


def _use_template(
    settings: Settings,
    template_name: str,
    parameters: dict[str, str],
    config_path: str,
) -> str:
    from .templates import render_template

    content = render_template(template_name, parameters)
    if content is None:
        return safe_json({"error": f"Template not found: {template_name}"})

    return _write_config(settings, config_path, content)


def _query_connector_docs(settings: Settings, connector_name: str, param_name: str | None = None) -> str:
    from .connector_docs import query_connector
    return safe_json(query_connector(connector_name, param_name))


def _list_config_versions(settings: Settings, config_path: str) -> str:
    path = Path(config_path)
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        rel = path
    safe_key = str(rel).replace("\\", "/").replace("/", "_")
    history_dir = Path(".config_history") / safe_key
    if not history_dir.is_dir():
        return safe_json({"versions": [], "count": 0, "message": "No version history found"})
    versions = []
    for f in sorted(history_dir.glob(f"v*_*{path.suffix}")):
        match = re.match(r"v(\d+)_(\d{8}_\d{6})", f.stem)
        if match:
            ver_num = int(match.group(1))
            ts_raw = match.group(2)
            ts = f"{ts_raw[:4]}-{ts_raw[4:6]}-{ts_raw[6:8]} {ts_raw[9:11]}:{ts_raw[11:13]}:{ts_raw[13:15]}"
            versions.append({
                "version": ver_num,
                "timestamp": ts,
                "size_bytes": f.stat().st_size,
                "path": str(f),
            })
    return safe_json({"config_path": config_path, "versions": versions, "count": len(versions)})


def _run_batch(settings: Settings, config_paths: list[str], stop_on_failure: bool = True) -> str:
    if not config_paths:
        return safe_json({"error": "No config paths provided"})
    if len(config_paths) > 20:
        return safe_json({"error": "Too many configs (max 20)"})
    results = []
    passed = 0
    failed = 0
    stopped_early = False
    for i, cp in enumerate(config_paths):
        job_result_raw = _run_seatunnel_job(settings, cp)
        try:
            job_data = json.loads(job_result_raw)
        except (json.JSONDecodeError, TypeError):
            job_data = {"success": False, "error": "Failed to parse result"}
        entry: dict[str, Any] = {
            "index": i + 1,
            "config_path": cp,
            "success": job_data.get("success", False),
        }
        if job_data.get("error"):
            entry["error"] = job_data["error"][:200]
        if job_data.get("metrics"):
            entry["metrics"] = job_data["metrics"]
        if job_data.get("exit_code") is not None:
            entry["exit_code"] = job_data["exit_code"]
        results.append(entry)
        if job_data.get("success"):
            passed += 1
        else:
            failed += 1
            if stop_on_failure:
                stopped_early = True
                break
    return safe_json({
        "total": len(config_paths),
        "executed": len(results),
        "passed": passed,
        "failed": failed,
        "stopped_early": stopped_early,
        "results": results,
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
    "test_connection": _test_connection,
    "list_templates": _list_templates,
    "use_template": _use_template,
    "query_connector_docs": _query_connector_docs,
    "list_config_versions": _list_config_versions,
    "run_batch": _run_batch,
}


def execute_tool(tool_name: str, tool_input: dict[str, Any], settings: Settings) -> str:
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return safe_json({"error": f"Unknown tool: {tool_name}"})
    try:
        return fn(settings, **tool_input)
    except Exception as e:
        return safe_json({"error": f"Tool '{tool_name}' failed: {e}"})
