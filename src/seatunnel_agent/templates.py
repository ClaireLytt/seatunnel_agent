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
    table = "${dst_table}"
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
    PipelineTemplate(
        name="csv_to_mysql",
        description="LocalFile CSV -> Jdbc MySQL (load CSV files into MySQL)",
        category="file",
        parameters=[
            {"name": "file_path", "default": "/data/input", "description": "Path to CSV files"},
            {"name": "delimiter", "default": ",", "description": "CSV field delimiter"},
            {"name": "mysql_url", "default": "jdbc:mysql://localhost:3306/mydb", "description": "MySQL JDBC URL"},
            {"name": "mysql_user", "default": "root", "description": "MySQL username"},
            {"name": "mysql_password", "default": "", "description": "MySQL password"},
            {"name": "table_name", "default": "", "description": "Target MySQL table name"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 1
}

source {
  LocalFile {
    path = "${file_path}"
    file_format_type = "csv"
    field_delimiter = "${delimiter}"
  }
}

transform {}

sink {
  Jdbc {
    url = "${mysql_url}"
    driver = "com.mysql.cj.jdbc.Driver"
    user = "${mysql_user}"
    password = "${mysql_password}"
    table = "${table_name}"
    generate_sink_sql = true
  }
}
""",
    ),
    PipelineTemplate(
        name="mysql_to_csv",
        description="Jdbc MySQL -> LocalFile CSV (export MySQL data to CSV files)",
        category="file",
        parameters=[
            {"name": "mysql_url", "default": "jdbc:mysql://localhost:3306/mydb", "description": "MySQL JDBC URL"},
            {"name": "mysql_user", "default": "root", "description": "MySQL username"},
            {"name": "mysql_password", "default": "", "description": "MySQL password"},
            {"name": "query", "default": "SELECT * FROM users", "description": "SQL query to export"},
            {"name": "output_path", "default": "/data/output", "description": "Output directory for CSV files"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 1
}

source {
  Jdbc {
    url = "${mysql_url}"
    driver = "com.mysql.cj.jdbc.Driver"
    user = "${mysql_user}"
    password = "${mysql_password}"
    query = "${query}"
  }
}

transform {}

sink {
  LocalFile {
    path = "${output_path}"
    file_format_type = "csv"
  }
}
""",
    ),
    PipelineTemplate(
        name="kafka_to_mysql",
        description="Kafka -> Jdbc MySQL (stream Kafka messages into MySQL)",
        category="streaming",
        parameters=[
            {"name": "bootstrap_servers", "default": "localhost:9092", "description": "Kafka bootstrap servers"},
            {"name": "topic", "default": "", "description": "Kafka topic name"},
            {"name": "group_id", "default": "seatunnel-group", "description": "Kafka consumer group ID"},
            {"name": "mysql_url", "default": "jdbc:mysql://localhost:3306/mydb", "description": "MySQL JDBC URL"},
            {"name": "mysql_user", "default": "root", "description": "MySQL username"},
            {"name": "mysql_password", "default": "", "description": "MySQL password"},
            {"name": "table_name", "default": "", "description": "Target MySQL table name"},
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
    format = "json"
    consumer.group = "${group_id}"
    start_mode = "latest"
  }
}

transform {}

sink {
  Jdbc {
    url = "${mysql_url}"
    driver = "com.mysql.cj.jdbc.Driver"
    user = "${mysql_user}"
    password = "${mysql_password}"
    table = "${table_name}"
    generate_sink_sql = true
  }
}
""",
    ),
    PipelineTemplate(
        name="fake_to_clickhouse",
        description="FakeSource -> ClickHouse (testing data ingestion into ClickHouse)",
        category="testing",
        parameters=[
            {"name": "rows", "default": "10", "description": "Number of rows to generate"},
            {"name": "ch_host", "default": "localhost:8123", "description": "ClickHouse host:port"},
            {"name": "ch_database", "default": "default", "description": "ClickHouse database name"},
            {"name": "ch_table", "default": "", "description": "ClickHouse table name"},
            {"name": "ch_username", "default": "default", "description": "ClickHouse username"},
            {"name": "ch_password", "default": "", "description": "ClickHouse password"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 1
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
  ClickHouse {
    host = "${ch_host}"
    database = "${ch_database}"
    table = "${ch_table}"
    username = "${ch_username}"
    password = "${ch_password}"
  }
}
""",
    ),
    PipelineTemplate(
        name="mysql_to_starrocks",
        description="Jdbc MySQL -> StarRocks (batch migration from MySQL to StarRocks)",
        category="database",
        parameters=[
            {"name": "mysql_url", "default": "jdbc:mysql://localhost:3306/mydb", "description": "MySQL JDBC URL"},
            {"name": "mysql_user", "default": "root", "description": "MySQL username"},
            {"name": "mysql_password", "default": "", "description": "MySQL password"},
            {"name": "query", "default": "SELECT * FROM users", "description": "SQL query to export"},
            {"name": "sr_node_urls", "default": "localhost:8030", "description": "StarRocks FE node addresses"},
            {"name": "sr_database", "default": "", "description": "StarRocks database name"},
            {"name": "sr_table", "default": "", "description": "StarRocks table name"},
            {"name": "sr_username", "default": "root", "description": "StarRocks username"},
            {"name": "sr_password", "default": "", "description": "StarRocks password"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 2
}

source {
  Jdbc {
    url = "${mysql_url}"
    driver = "com.mysql.cj.jdbc.Driver"
    user = "${mysql_user}"
    password = "${mysql_password}"
    query = "${query}"
  }
}

transform {}

sink {
  StarRocks {
    nodeUrls = ["${sr_node_urls}"]
    database = "${sr_database}"
    table = "${sr_table}"
    username = "${sr_username}"
    password = "${sr_password}"
  }
}
""",
    ),
    PipelineTemplate(
        name="fake_to_console_with_transform",
        description="FakeSource -> SQL Transform -> Console (testing with data transformation)",
        category="testing",
        parameters=[
            {"name": "rows", "default": "10", "description": "Number of rows to generate"},
            {"name": "sql_query", "default": "SELECT id, name, age * 2 AS double_age FROM fake", "description": "SQL transformation query"},
        ],
        content="""\
env {
  job.mode = "BATCH"
  parallelism = 1
}

source {
  FakeSource {
    schema = {
      fields {
        id = "int"
        name = "string"
        age = "int"
      }
    }
    rows = ${rows}
  }
}

transform {
  SQL {
    query = "${sql_query}"
  }
}

sink {
  Console {}
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
