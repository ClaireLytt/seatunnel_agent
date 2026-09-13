"""Structured documentation for common SeaTunnel connectors.

Provides parameter-level details (types, required/optional, valid values, notes)
that the agent can look up before generating configs, reducing hallucination.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConnectorParam:
    name: str
    type: str
    required: bool
    description: str
    example: str
    enum_values: list[str] | None = None


@dataclass
class ConnectorDoc:
    name: str
    connector_type: str
    description: str
    required_params: list[ConnectorParam]
    optional_params: list[ConnectorParam] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


CONNECTOR_DOCS: dict[str, ConnectorDoc] = {
    "FakeSource": ConnectorDoc(
        name="FakeSource",
        connector_type="source",
        description="Generates fake data for testing without external dependencies.",
        required_params=[],
        optional_params=[
            ConnectorParam("schema", "object", False,
                           "Define output field names and types",
                           'schema = { fields { name = "string", age = "int" } }'),
            ConnectorParam("rows", "int", False,
                           "Number of rows to generate (default unlimited in streaming)",
                           "rows = 100"),
            ConnectorParam("row.num", "int", False,
                           "Alias for rows — number of data items to generate",
                           "row.num = 50"),
        ],
        notes=[
            "No external dependencies needed — ideal for testing pipelines.",
            "Supported field types: string, boolean, tinyint, smallint, int, bigint, float, double, decimal, date, time, timestamp, bytes, null, array, map.",
        ],
    ),
    "Console": ConnectorDoc(
        name="Console",
        connector_type="sink",
        description="Prints data to stdout. Useful for testing and debugging pipelines.",
        required_params=[],
        optional_params=[
            ConnectorParam("line.delimiter", "string", False,
                           "Line separator between output records",
                           'line.delimiter = "\\n"'),
        ],
        notes=[
            "No required parameters — Console {} is a valid minimal config.",
            "Commonly paired with FakeSource for quick pipeline testing.",
        ],
    ),
    "Jdbc": ConnectorDoc(
        name="Jdbc",
        connector_type="both",
        description="Read from or write to any JDBC-compatible database (MySQL, PostgreSQL, Oracle, etc.).",
        required_params=[
            ConnectorParam("url", "string", True,
                           "JDBC connection URL",
                           'url = "jdbc:mysql://localhost:3306/mydb"'),
            ConnectorParam("driver", "string", True,
                           "JDBC driver class name",
                           'driver = "com.mysql.cj.jdbc.Driver"'),
            ConnectorParam("user", "string", True,
                           "Database username",
                           'user = "root"'),
            ConnectorParam("password", "string", True,
                           "Database password",
                           'password = "your_password"'),
        ],
        optional_params=[
            ConnectorParam("query", "string", False,
                           "SQL query for source mode",
                           'query = "SELECT * FROM users"'),
            ConnectorParam("table", "string", False,
                           "Target table name for sink mode",
                           'table = "users"'),
            ConnectorParam("database", "string", False,
                           "Database name (sink mode)",
                           'database = "mydb"'),
            ConnectorParam("generate_sink_sql", "boolean", False,
                           "Auto-generate INSERT SQL for sink (default false)",
                           "generate_sink_sql = true"),
            ConnectorParam("connection_check_timeout_sec", "int", False,
                           "Connection validation timeout in seconds (default 30)",
                           "connection_check_timeout_sec = 10"),
            ConnectorParam("batch_size", "int", False,
                           "Batch size for sink writes (default 1000)",
                           "batch_size = 500"),
        ],
        notes=[
            "As source: 'query' is required. As sink: 'table' or 'database' + 'generate_sink_sql' is needed.",
            "Common drivers: com.mysql.cj.jdbc.Driver (MySQL), org.postgresql.Driver (PostgreSQL), oracle.jdbc.OracleDriver (Oracle).",
            "Ensure the corresponding JDBC driver JAR is in $SEATUNNEL_HOME/lib/.",
        ],
    ),
    "MySQL-CDC": ConnectorDoc(
        name="MySQL-CDC",
        connector_type="source",
        description="Capture real-time changes from MySQL using Change Data Capture (CDC).",
        required_params=[
            ConnectorParam("hostname", "string", True,
                           "MySQL server hostname",
                           'hostname = "localhost"'),
            ConnectorParam("port", "int", True,
                           "MySQL server port",
                           "port = 3306"),
            ConnectorParam("database-name", "string", True,
                           "Database name to capture (supports regex)",
                           'database-name = "inventory"'),
            ConnectorParam("table-name", "string", True,
                           "Table name to capture (supports regex)",
                           'table-name = "products"'),
            ConnectorParam("username", "string", True,
                           "MySQL username with REPLICATION privileges",
                           'username = "root"'),
            ConnectorParam("password", "string", True,
                           "MySQL password",
                           'password = "password"'),
        ],
        optional_params=[
            ConnectorParam("server-id", "string", False,
                           "Unique numeric ID for the CDC client (avoid conflicts with other CDC readers)",
                           'server-id = "5400-5404"'),
            ConnectorParam("startup.mode", "enum", False,
                           "How to start reading changes",
                           'startup.mode = "initial"',
                           ["initial", "earliest", "latest", "specific-offset", "timestamp"]),
            ConnectorParam("snapshot.split.size", "int", False,
                           "Split size for snapshot reading (default 8096)",
                           "snapshot.split.size = 8096"),
        ],
        notes=[
            "MySQL user needs REPLICATION SLAVE and REPLICATION CLIENT privileges.",
            "Use job.mode = 'STREAMING' in env block for CDC sources.",
            "database-name and table-name support regex: 'db_.*' matches all databases starting with db_.",
        ],
    ),
    "Kafka": ConnectorDoc(
        name="Kafka",
        connector_type="both",
        description="Read from or write to Apache Kafka topics.",
        required_params=[
            ConnectorParam("bootstrap.servers", "string", True,
                           "Kafka broker addresses",
                           'bootstrap.servers = "localhost:9092"'),
            ConnectorParam("topic", "string", True,
                           "Kafka topic name",
                           'topic = "my-topic"'),
        ],
        optional_params=[
            ConnectorParam("format", "enum", False,
                           "Data serialization format (default json)",
                           'format = "json"',
                           ["json", "avro", "canal_json", "debezium_json", "ogg_json", "text", "csv"]),
            ConnectorParam("consumer.group", "string", False,
                           "Consumer group ID (source only)",
                           'consumer.group = "seatunnel-group"'),
            ConnectorParam("semantics", "enum", False,
                           "Delivery semantics for sink",
                           'semantics = "EXACTLY_ONCE"',
                           ["AT_LEAST_ONCE", "EXACTLY_ONCE", "NON"]),
            ConnectorParam("start_mode", "enum", False,
                           "Consumer start position (source only)",
                           'start_mode = "earliest"',
                           ["earliest", "latest", "group_offsets", "timestamp", "specific_offsets"]),
            ConnectorParam("kafka.config", "object", False,
                           "Additional Kafka producer/consumer properties",
                           'kafka.config = { "security.protocol" = "SASL_SSL" }'),
        ],
        notes=[
            "As source: consider setting consumer.group and start_mode.",
            "For CDC format, use format = 'canal_json' or 'debezium_json'.",
            "Use job.mode = 'STREAMING' for continuous consumption.",
        ],
    ),
    "LocalFile": ConnectorDoc(
        name="LocalFile",
        connector_type="both",
        description="Read from or write to local filesystem files.",
        required_params=[
            ConnectorParam("path", "string", True,
                           "Directory path for reading/writing files",
                           'path = "/data/output"'),
            ConnectorParam("file_format_type", "enum", True,
                           "File format",
                           'file_format_type = "csv"',
                           ["csv", "json", "parquet", "orc", "text", "xml", "excel", "binary"]),
        ],
        optional_params=[
            ConnectorParam("schema", "object", False,
                           "Define data schema for CSV/text reading",
                           'schema = { fields { name = "string", age = "int" } }'),
            ConnectorParam("field_delimiter", "string", False,
                           "Field separator for CSV/text files (default ',')",
                           'field_delimiter = "\\t"'),
            ConnectorParam("file_name_expression", "string", False,
                           "Output file naming pattern (sink only)",
                           'file_name_expression = "${now}_${uuid}"'),
            ConnectorParam("row_delimiter", "string", False,
                           "Row separator (default newline)",
                           'row_delimiter = "\\n"'),
        ],
        notes=[
            "For source, 'path' should point to a directory containing files.",
            "For CSV source without header, define schema explicitly.",
        ],
    ),
    "HTTP": ConnectorDoc(
        name="HTTP",
        connector_type="source",
        description="Read data from HTTP/REST API endpoints.",
        required_params=[
            ConnectorParam("url", "string", True,
                           "HTTP endpoint URL",
                           'url = "https://api.example.com/data"'),
        ],
        optional_params=[
            ConnectorParam("method", "enum", False,
                           "HTTP method (default GET)",
                           'method = "GET"',
                           ["GET", "POST", "PUT"]),
            ConnectorParam("headers", "object", False,
                           "HTTP request headers",
                           'headers = { "Authorization" = "Bearer token123" }'),
            ConnectorParam("params", "object", False,
                           "URL query parameters",
                           'params = { "page" = "1", "size" = "100" }'),
            ConnectorParam("body", "string", False,
                           "Request body for POST/PUT",
                           'body = "{\\"query\\": \\"test\\"}"'),
            ConnectorParam("format", "enum", False,
                           "Response parsing format",
                           'format = "json"',
                           ["json", "text"]),
            ConnectorParam("content_type", "string", False,
                           "Request Content-Type header",
                           'content_type = "application/json"'),
        ],
        notes=[
            "For paginated APIs, consider using the paginate settings.",
            "Authentication can be passed via headers.",
        ],
    ),
    "ClickHouse": ConnectorDoc(
        name="ClickHouse",
        connector_type="sink",
        description="Write data to ClickHouse column-oriented database.",
        required_params=[
            ConnectorParam("host", "string", True,
                           "ClickHouse server hostname",
                           'host = "localhost:8123"'),
            ConnectorParam("database", "string", True,
                           "Target database name",
                           'database = "default"'),
            ConnectorParam("table", "string", True,
                           "Target table name",
                           'table = "events"'),
        ],
        optional_params=[
            ConnectorParam("username", "string", False,
                           "ClickHouse username",
                           'username = "default"'),
            ConnectorParam("password", "string", False,
                           "ClickHouse password",
                           'password = ""'),
            ConnectorParam("bulk_size", "int", False,
                           "Batch insert size (default 20000)",
                           "bulk_size = 10000"),
            ConnectorParam("split_mode", "string", False,
                           "Auto-split for distributed tables",
                           'split_mode = "true"'),
        ],
        notes=[
            "Host format includes port: 'localhost:8123' for HTTP interface.",
            "ClickHouse is columnar — best for analytical/append workloads.",
        ],
    ),
    "Doris": ConnectorDoc(
        name="Doris",
        connector_type="sink",
        description="Write data to Apache Doris (or StarRocks) via Stream Load.",
        required_params=[
            ConnectorParam("fenodes", "string", True,
                           "Doris FE node addresses",
                           'fenodes = "localhost:8030"'),
            ConnectorParam("database", "string", True,
                           "Target database name",
                           'database = "test_db"'),
            ConnectorParam("table", "string", True,
                           "Target table name",
                           'table = "users"'),
            ConnectorParam("user", "string", True,
                           "Doris username",
                           'user = "root"'),
            ConnectorParam("password", "string", True,
                           "Doris password",
                           'password = ""'),
        ],
        optional_params=[
            ConnectorParam("batch_max_rows", "int", False,
                           "Maximum rows per Stream Load batch (default 1024)",
                           "batch_max_rows = 2048"),
            ConnectorParam("batch_max_bytes", "int", False,
                           "Maximum bytes per batch (default 5MB)",
                           "batch_max_bytes = 10485760"),
        ],
        notes=[
            "Uses Stream Load HTTP API, connects to FE nodes.",
            "Ensure the Doris user has LOAD_PRIV on the target table.",
        ],
    ),
    "Elasticsearch": ConnectorDoc(
        name="Elasticsearch",
        connector_type="sink",
        description="Write data to Elasticsearch indices.",
        required_params=[
            ConnectorParam("hosts", "string", True,
                           "Elasticsearch HTTP endpoint(s)",
                           'hosts = ["http://localhost:9200"]'),
            ConnectorParam("index", "string", True,
                           "Target index name",
                           'index = "my-index"'),
        ],
        optional_params=[
            ConnectorParam("username", "string", False,
                           "Elasticsearch username",
                           'username = "elastic"'),
            ConnectorParam("password", "string", False,
                           "Elasticsearch password",
                           'password = "changeme"'),
            ConnectorParam("max_batch_size", "int", False,
                           "Bulk request batch size (default 10)",
                           "max_batch_size = 100"),
            ConnectorParam("max_retry_count", "int", False,
                           "Maximum retry count for failed requests (default 3)",
                           "max_retry_count = 5"),
        ],
        notes=[
            "hosts accepts a JSON array of URLs.",
            "For Elasticsearch 8.x with security enabled, provide username and password.",
        ],
    ),
    "S3File": ConnectorDoc(
        name="S3File",
        connector_type="both",
        description="Read from or write to Amazon S3 (or S3-compatible) storage.",
        required_params=[
            ConnectorParam("path", "string", True,
                           "S3 path (directory for reading, prefix for writing)",
                           'path = "/my-bucket/data/"'),
            ConnectorParam("bucket", "string", True,
                           "S3 bucket name",
                           'bucket = "my-bucket"'),
            ConnectorParam("access_key", "string", True,
                           "AWS access key ID",
                           'access_key = "AKIAIOSFODNN7EXAMPLE"'),
            ConnectorParam("secret_key", "string", True,
                           "AWS secret access key",
                           'secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'),
            ConnectorParam("file_format_type", "enum", True,
                           "File format",
                           'file_format_type = "parquet"',
                           ["csv", "json", "parquet", "orc", "text"]),
        ],
        optional_params=[
            ConnectorParam("hadoop_s3_properties", "object", False,
                           "Extra Hadoop S3 configuration",
                           'hadoop_s3_properties = { "fs.s3a.endpoint" = "s3.amazonaws.com" }'),
            ConnectorParam("schema", "object", False,
                           "Define data schema for CSV/text reading",
                           'schema = { fields { name = "string" } }'),
        ],
        notes=[
            "For S3-compatible services (MinIO, etc.), set endpoint in hadoop_s3_properties.",
            "Credentials can also be set via IAM roles if running on AWS.",
        ],
    ),
    "PostgreSQL-CDC": ConnectorDoc(
        name="PostgreSQL-CDC",
        connector_type="source",
        description="Change Data Capture for PostgreSQL.",
        required_params=[
            ConnectorParam("hostname", "string", True,
                           "PostgreSQL server hostname",
                           'hostname = "localhost"'),
            ConnectorParam("port", "int", True,
                           "PostgreSQL server port",
                           "port = 5432"),
            ConnectorParam("database-names", "string", True,
                           "Database name(s) to capture",
                           'database-names = ["inventory"]'),
            ConnectorParam("username", "string", True,
                           "PostgreSQL username with replication privileges",
                           'username = "postgres"'),
            ConnectorParam("password", "string", True,
                           "PostgreSQL password",
                           'password = "password"'),
            ConnectorParam("table-names", "string", True,
                           "Table name(s) to capture",
                           'table-names = ["public.products"]'),
            ConnectorParam("slot.name", "string", True,
                           "PostgreSQL logical replication slot name",
                           'slot.name = "seatunnel_slot"'),
        ],
        optional_params=[
            ConnectorParam("decoding.plugin.name", "enum", False,
                           "Logical decoding output plugin (default pgoutput)",
                           'decoding.plugin.name = "pgoutput"',
                           ["pgoutput", "decoderbufs"]),
            ConnectorParam("startup.mode", "enum", False,
                           "How to start reading changes",
                           'startup.mode = "initial"',
                           ["initial", "latest-offset"]),
        ],
        notes=[
            "Requires PostgreSQL 10+ with logical replication enabled",
            "Set wal_level=logical in postgresql.conf",
        ],
    ),
    "MongoDB": ConnectorDoc(
        name="MongoDB",
        connector_type="source",
        description="Read data from MongoDB collections.",
        required_params=[
            ConnectorParam("uri", "string", True,
                           "MongoDB connection URI",
                           'uri = "mongodb://localhost:27017"'),
            ConnectorParam("database", "string", True,
                           "MongoDB database name",
                           'database = "test_db"'),
            ConnectorParam("collection", "string", True,
                           "MongoDB collection name",
                           'collection = "users"'),
        ],
        optional_params=[
            ConnectorParam("schema", "object", False,
                           "Define output field names and types",
                           'schema = { fields { name = "string", age = "int" } }'),
            ConnectorParam("cursor.no_timeout", "boolean", False,
                           "Prevent cursor timeout for long-running reads",
                           "cursor.no_timeout = true"),
            ConnectorParam("fetch.size", "int", False,
                           "Number of documents to fetch per batch",
                           "fetch.size = 2048"),
        ],
        notes=[
            "Supports MongoDB 3.6+",
            "URI format: mongodb://host:port",
        ],
    ),
    "HdfsFile": ConnectorDoc(
        name="HdfsFile",
        connector_type="both",
        description="Read/write files on HDFS.",
        required_params=[
            ConnectorParam("path", "string", True,
                           "HDFS directory path for reading/writing files",
                           'path = "/data/output"'),
            ConnectorParam("fs.defaultFS", "string", True,
                           "HDFS NameNode address",
                           'fs.defaultFS = "hdfs://namenode:8020"'),
            ConnectorParam("file_format_type", "enum", True,
                           "File format",
                           'file_format_type = "parquet"',
                           ["json", "csv", "parquet", "orc", "text"]),
        ],
        optional_params=[
            ConnectorParam("delimiter", "string", False,
                           "Field delimiter for CSV/text files",
                           'delimiter = ","'),
            ConnectorParam("skip_header_row_number", "int", False,
                           "Number of header rows to skip (source only)",
                           "skip_header_row_number = 1"),
            ConnectorParam("compress_codec", "enum", False,
                           "Compression codec for output files",
                           'compress_codec = "gzip"',
                           ["none", "gzip", "snappy", "lz4"]),
        ],
    ),
    "Hive": ConnectorDoc(
        name="Hive",
        connector_type="both",
        description="Read/write Hive tables via metastore.",
        required_params=[
            ConnectorParam("metastore_uri", "string", True,
                           "Hive Metastore URI",
                           'metastore_uri = "thrift://localhost:9083"'),
            ConnectorParam("table_name", "string", True,
                           "Hive table name (database.table format)",
                           'table_name = "default.users"'),
        ],
        optional_params=[
            ConnectorParam("read_partitions", "string", False,
                           "Partition filter for reading specific partitions",
                           'read_partitions = ["dt=2024-01-01"]'),
            ConnectorParam("partition_by", "string", False,
                           "Partition columns for writing",
                           'partition_by = ["dt"]'),
            ConnectorParam("compress_codec", "string", False,
                           "Compression codec for output files",
                           'compress_codec = "snappy"'),
        ],
        notes=[
            "Requires Hive Metastore service running",
        ],
    ),
    "StarRocks": ConnectorDoc(
        name="StarRocks",
        connector_type="sink",
        description="Load data into StarRocks.",
        required_params=[
            ConnectorParam("nodeUrls", "string", True,
                           "StarRocks FE node HTTP addresses",
                           'nodeUrls = ["localhost:8030"]'),
            ConnectorParam("database", "string", True,
                           "Target database name",
                           'database = "test_db"'),
            ConnectorParam("table", "string", True,
                           "Target table name",
                           'table = "users"'),
            ConnectorParam("username", "string", True,
                           "StarRocks username",
                           'username = "root"'),
            ConnectorParam("password", "string", True,
                           "StarRocks password",
                           'password = ""'),
        ],
        optional_params=[
            ConnectorParam("batch_max_rows", "int", False,
                           "Maximum rows per Stream Load batch (default 1024)",
                           "batch_max_rows = 2048"),
            ConnectorParam("batch_max_bytes", "int", False,
                           "Maximum bytes per batch (default 5MB)",
                           "batch_max_bytes = 10485760"),
            ConnectorParam("labelPrefix", "string", False,
                           "Label prefix for Stream Load jobs",
                           'labelPrefix = "seatunnel_"'),
        ],
        notes=[
            "Uses Stream Load for data ingestion",
            "Supports StarRocks 2.x and 3.x",
        ],
    ),
    "Redis": ConnectorDoc(
        name="Redis",
        connector_type="both",
        description="Read/write Redis data.",
        required_params=[
            ConnectorParam("host", "string", True,
                           "Redis server hostname",
                           'host = "localhost"'),
            ConnectorParam("port", "int", True,
                           "Redis server port",
                           "port = 6379"),
            ConnectorParam("key", "string", True,
                           "Redis key name",
                           'key = "seatunnel_data"'),
            ConnectorParam("data_type", "enum", True,
                           "Redis data type",
                           'data_type = "hash"',
                           ["string", "list", "set", "zset", "hash"]),
        ],
        optional_params=[
            ConnectorParam("auth", "string", False,
                           "Redis authentication password",
                           'auth = "your_password"'),
            ConnectorParam("db_num", "int", False,
                           "Redis database number (default 0)",
                           "db_num = 0"),
            ConnectorParam("expire", "int", False,
                           "Key expiration time in seconds",
                           "expire = 3600"),
        ],
    ),
    "Paimon": ConnectorDoc(
        name="Paimon",
        connector_type="both",
        description="Read/write Apache Paimon tables.",
        required_params=[
            ConnectorParam("warehouse", "string", True,
                           "Paimon warehouse path",
                           'warehouse = "hdfs:///path/to/warehouse"'),
            ConnectorParam("database", "string", True,
                           "Paimon database name",
                           'database = "test_db"'),
            ConnectorParam("table", "string", True,
                           "Paimon table name",
                           'table = "orders"'),
        ],
        optional_params=[
            ConnectorParam("catalog_type", "enum", False,
                           "Catalog type for table metadata storage",
                           'catalog_type = "filesystem"',
                           ["filesystem", "hive"]),
            ConnectorParam("query_filter", "string", False,
                           "Filter expression for reading data",
                           'query_filter = "dt = \'2024-01-01\'"'),
        ],
        notes=[
            "Apache Paimon (formerly Flink Table Store)",
        ],
    ),
    "Iceberg": ConnectorDoc(
        name="Iceberg",
        connector_type="both",
        description="Read/write Apache Iceberg tables.",
        required_params=[
            ConnectorParam("catalog_name", "string", True,
                           "Iceberg catalog name",
                           'catalog_name = "default_catalog"'),
            ConnectorParam("namespace", "string", True,
                           "Iceberg namespace (database)",
                           'namespace = "default"'),
            ConnectorParam("table", "string", True,
                           "Iceberg table name",
                           'table = "events"'),
            ConnectorParam("uri", "string", True,
                           "Catalog URI (e.g. Hive Metastore or REST catalog)",
                           'uri = "thrift://localhost:9083"'),
        ],
        optional_params=[
            ConnectorParam("case_sensitive", "boolean", False,
                           "Enable case-sensitive column name matching (default true)",
                           "case_sensitive = false"),
            ConnectorParam("snapshot_id", "int", False,
                           "Read from a specific Iceberg snapshot",
                           "snapshot_id = 1234567890"),
        ],
        notes=[
            "Supports Iceberg v1 and v2 table format",
        ],
    ),
}


def query_connector(connector_name: str, param_name: str | None = None) -> dict:
    key = _find_connector_key(connector_name)
    if key is None:
        return {
            "error": f"Connector '{connector_name}' not found in documentation.",
            "available_connectors": list_documented_connectors(),
        }

    doc = CONNECTOR_DOCS[key]

    if param_name:
        for p in doc.required_params + doc.optional_params:
            if p.name == param_name:
                return {
                    "connector_name": doc.name,
                    "param_detail": {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "description": p.description,
                        "example": p.example,
                        **({"enum_values": p.enum_values} if p.enum_values else {}),
                    },
                }
        return {
            "error": f"Parameter '{param_name}' not found for connector '{doc.name}'.",
            "available_params": [p.name for p in doc.required_params + doc.optional_params],
        }

    return {
        "connector_name": doc.name,
        "connector_type": doc.connector_type,
        "description": doc.description,
        "required_params": [
            {"name": p.name, "type": p.type, "description": p.description, "example": p.example}
            for p in doc.required_params
        ],
        "optional_params": [
            {"name": p.name, "type": p.type, "description": p.description, "example": p.example}
            for p in doc.optional_params
        ],
        "notes": doc.notes,
    }


def list_documented_connectors() -> list[str]:
    return sorted(CONNECTOR_DOCS.keys())


def _find_connector_key(name: str) -> str | None:
    if name in CONNECTOR_DOCS:
        return name
    lower = name.lower()
    for key in CONNECTOR_DOCS:
        if key.lower() == lower:
            return key
    return None
