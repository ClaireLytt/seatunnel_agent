"""JSON tool schemas for the SeaTunnel config agent (sent to the LLM).

Moved verbatim out of tools.py, which re-exports TOOL_DEFINITIONS.
"""

from __future__ import annotations

from typing import Any

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
    {
        "name": "restore_config_version",
        "description": (
            "Restore a config file to a previous version from its version history. "
            "Use list_config_versions first to see available versions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file to restore",
                },
                "version": {
                    "type": "integer",
                    "description": "Version number to restore (from list_config_versions)",
                },
            },
            "required": ["config_path", "version"],
        },
    },
    {
        "name": "delete_config",
        "description": (
            "Delete a SeaTunnel config file. "
            "Version history is preserved and can still be listed/restored."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file to delete",
                },
            },
            "required": ["config_path"],
        },
    },
    {
        "name": "compare_config_versions",
        "description": (
            "Compare two versions of a config file and show the diff. "
            "Use list_config_versions first to see available version numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file",
                },
                "version_a": {
                    "type": "integer",
                    "description": "First version number to compare",
                },
                "version_b": {
                    "type": "integer",
                    "description": "Second version number to compare",
                },
            },
            "required": ["config_path", "version_a", "version_b"],
        },
    },
    {
        "name": "explain_config",
        "description": (
            "Parse and explain a SeaTunnel config file in structured form. "
            "Returns job mode, parallelism, source/transform/sink details. "
            "Use when the user wants to understand an existing config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the config file to explain",
                },
            },
            "required": ["config_path"],
        },
    },
]
