"""Built-in pipeline config templates for common SeaTunnel jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Template


@dataclass
class PipelineTemplate:
    name: str
    description: str
    category: str
    parameters: list[dict[str, str]]
    content: str

    def render(self, params: dict[str, str]) -> str:
        return Template(self.content).safe_substitute(params)


TEMPLATES: list[PipelineTemplate] = [
    PipelineTemplate(
        name="fake_to_console",
        description="FakeSource -> Console (testing, no external dependencies)",
        category="testing",
        parameters=[
            {"name": "rows", "default": "10", "description": "Number of rows to generate"},
            {"name": "parallelism", "default": "1", "description": "Job parallelism"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = ${parallelism}
}

source {
  FakeSource {
    schema = {
      fields {
        name = "string"
        age = "int"
        email = "string"
      }
    }
    rows = ${rows}
  }
}

transform {}

sink {
  Console {}
}
""",
    ),
    PipelineTemplate(
        name="mysql_to_console",
        description="MySQL-CDC -> Console (real-time change capture to stdout)",
        category="database",
        parameters=[
            {"name": "hostname", "default": "localhost", "description": "MySQL host"},
            {"name": "port", "default": "3306", "description": "MySQL port"},
            {"name": "database", "default": "", "description": "Database name"},
            {"name": "table", "default": "", "description": "Table name"},
            {"name": "username", "default": "root", "description": "MySQL user"},
            {"name": "password", "default": "", "description": "MySQL password"},
        ],
        content="""\
env {
  job.mode = "STREAMING"
  parallelism = 1
}

source {
  MySQL-CDC {
    hostname = "${hostname}"
    port = ${port}
    database-name = "${database}"
    table-name = "${table}"
    username = "${username}"
    password = "${password}"
  }
}

transform {}

sink {
  Console {}
}
""",
    ),
    PipelineTemplate(
        name="mysql_to_mysql",
        description="Jdbc(MySQL) -> Jdbc(MySQL) (batch database migration)",
        category="database",
        parameters=[
            {"name": "src_url", "default": "jdbc:mysql://localhost:3306/src_db", "description": "Source JDBC URL"},
            {"name": "src_query", "default": "SELECT * FROM users", "description": "Source SQL query"},
            {"name": "src_user", "default": "root", "description": "Source DB user"},
            {"name": "src_password", "default": "", "description": "Source DB password"},
            {"name": "dst_url", "default": "jdbc:mysql://localhost:3306/dst_db", "description": "Destination JDBC URL"},
            {"name": "dst_table", "default": "users", "description": "Destination table name"},
            {"name": "dst_user", "default": "root", "description": "Destination DB user"},
            {"name": "dst_password", "default": "", "description": "Destination DB password"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 2
}

source {
  Jdbc {
    url = "${src_url}"
    driver = "com.mysql.cj.jdbc.Driver"
    user = "${src_user}"
    password = "${src_password}"
    query = "${src_query}"
  }
}

transform {}

sink {
  Jdbc {
    url = "${dst_url}"
    driver = "com.mysql.cj.jdbc.Driver"
    user = "${dst_user}"
    password = "${dst_password}"
    database = "${dst_table}"
    generate_sink_sql = true
  }
}
""",
    ),
    PipelineTemplate(
        name="kafka_to_console",
        description="Kafka -> Console (stream monitoring)",
        category="streaming",
        parameters=[
            {"name": "bootstrap_servers", "default": "localhost:9092", "description": "Kafka bootstrap servers"},
            {"name": "topic", "default": "", "description": "Kafka topic name"},
            {"name": "format", "default": "json", "description": "Message format (json, csv, text)"},
        ],
        content="""\
env {
  job.mode = "STREAMING"
  parallelism = 1
}

source {
  Kafka {
    bootstrap.servers = "${bootstrap_servers}"
    topic = "${topic}"
    format = "${format}"
    start_mode = "latest"
  }
}

transform {}

sink {
  Console {}
}
""",
    ),
    PipelineTemplate(
        name="localfile_to_console",
        description="LocalFile -> Console (read CSV/JSON files to stdout)",
        category="file",
        parameters=[
            {"name": "path", "default": "/data/input", "description": "Path to input files"},
            {"name": "file_format_type", "default": "csv", "description": "File format (csv, json, parquet)"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 1
}

source {
  LocalFile {
    path = "${path}"
    file_format_type = "${file_format_type}"
  }
}

transform {}

sink {
  Console {}
}
""",
    ),
    PipelineTemplate(
        name="mysql_to_kafka",
        description="MySQL-CDC -> Kafka (database change events to message queue)",
        category="streaming",
        parameters=[
            {"name": "hostname", "default": "localhost", "description": "MySQL host"},
            {"name": "port", "default": "3306", "description": "MySQL port"},
            {"name": "database", "default": "", "description": "Database name"},
            {"name": "table", "default": "", "description": "Table name"},
            {"name": "username", "default": "root", "description": "MySQL user"},
            {"name": "password", "default": "", "description": "MySQL password"},
            {"name": "bootstrap_servers", "default": "localhost:9092", "description": "Kafka bootstrap servers"},
            {"name": "topic", "default": "", "description": "Kafka topic name"},
        ],
        content="""\
env {
  job.mode = "STREAMING"
  parallelism = 1
}

source {
  MySQL-CDC {
    hostname = "${hostname}"
    port = ${port}
    database-name = "${database}"
    table-name = "${table}"
    username = "${username}"
    password = "${password}"
  }
}

transform {}

sink {
  Kafka {
    bootstrap.servers = "${bootstrap_servers}"
    topic = "${topic}"
    format = "json"
  }
}
""",
    ),
]

_TEMPLATE_MAP: dict[str, PipelineTemplate] = {t.name: t for t in TEMPLATES}


def get_template(name: str) -> PipelineTemplate | None:
    return _TEMPLATE_MAP.get(name)


def list_templates(category: str | None = None) -> list[PipelineTemplate]:
    if category:
        return [t for t in TEMPLATES if t.category == category]
    return list(TEMPLATES)


def render_template(name: str, params: dict[str, str]) -> str | None:
    tpl = get_template(name)
    if tpl is None:
        return None
    merged = {p["name"]: p.get("default", "") for p in tpl.parameters}
    merged.update(params)
    return tpl.render(merged)
