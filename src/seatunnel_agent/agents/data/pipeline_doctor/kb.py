"""Failure-signature knowledge base for pipeline diagnosis.

Each signature is a regex over the extracted exception cluster (exception
class + message + sample lines) plus the engine it belongs to, the likely
root cause and the concrete fix. Deterministic: matching never calls out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# severity rank: gate comparisons and finding ordering
SEVERITY_RANK = {"critical": 2, "error": 1, "warn": 0}


@dataclass(frozen=True)
class Signature:
    id: str              # stable slug, e.g. "spark_oom_heap"
    engine: str          # spark | hive | seatunnel | generic
    severity: str        # critical | error | warn
    pattern: re.Pattern  # matched against "<exception>: <message>\n<sample>"
    title_zh: str
    title_en: str
    cause_zh: str
    cause_en: str
    fix_zh: str
    fix_en: str
    # copy-paste fix patch: concrete config/commands applying the fix
    # (language-neutral; empty when no one-size template exists)
    patch: str = ""


def _sig(sig_id: str, engine: str, severity: str, pattern: str, *,
         title_zh: str, title_en: str, cause_zh: str, cause_en: str,
         fix_zh: str, fix_en: str, patch: str = "") -> Signature:
    return Signature(id=sig_id, engine=engine, severity=severity,
                     pattern=re.compile(pattern, re.I | re.S),
                     title_zh=title_zh, title_en=title_en,
                     cause_zh=cause_zh, cause_en=cause_en,
                     fix_zh=fix_zh, fix_en=fix_en, patch=patch)


SIGNATURES: tuple[Signature, ...] = (
    # ---------------------------------------------------------------- spark
    _sig("spark_oom_heap", "spark", "critical",
         r"java\.lang\.OutOfMemoryError(?!.*GC overhead)",
         title_zh="Executor/Driver 堆内存溢出",
         title_en="Executor/driver heap OutOfMemoryError",
         cause_zh="JVM 堆不足：单分区数据过大、广播表过大或 collect 拉回数据过多。",
         cause_en="JVM heap exhausted: oversized partitions, a too-large "
                  "broadcast table, or collecting too much to the driver.",
         fix_zh="调大 spark.executor.memory / spark.driver.memory；增加 "
                "shuffle 分区数（spark.sql.shuffle.partitions）切小分区；"
                "检查是否误用 collect()/broadcast 大表。",
         fix_en="Raise spark.executor.memory / spark.driver.memory; increase "
                "spark.sql.shuffle.partitions to shrink partitions; audit "
                "collect()/broadcast usage on large tables.",
         patch="spark-submit \\\n"
               "  --conf spark.executor.memory=8g \\\n"
               "  --conf spark.driver.memory=4g \\\n"
               "  --conf spark.sql.shuffle.partitions=400"),
    _sig("spark_gc_overhead", "spark", "critical",
         r"OutOfMemoryError.*GC overhead limit exceeded",
         title_zh="GC 开销超限（堆接近耗尽）",
         title_en="GC overhead limit exceeded (heap nearly full)",
         cause_zh="JVM 大部分时间在做 GC 仍回收不到内存，通常是数据倾斜或缓存过多。",
         cause_en="The JVM spends most time in GC without reclaiming memory — "
                  "usually data skew or excessive caching.",
         fix_zh="先看是否个别 task 远慢于其他（倾斜）；调大 executor 内存或减少 "
                "cache；倾斜键可加盐打散或开启 AQE skew join。",
         fix_en="Check for straggler tasks (skew); raise executor memory or "
                "reduce caching; salt skewed keys or enable AQE skew join.",
         patch="spark-submit \\\n"
               "  --conf spark.executor.memory=8g \\\n"
               "  --conf spark.sql.adaptive.enabled=true \\\n"
               "  --conf spark.sql.adaptive.skewJoin.enabled=true"),
    _sig("spark_yarn_container_kill", "spark", "critical",
         r"Container killed by YARN for exceeding (?:physical |virtual )?memory",
         title_zh="容器超物理内存被 YARN 杀死",
         title_en="Container killed by YARN for exceeding memory limits",
         cause_zh="堆外内存（netty/python/本地库）超出 YARN 容器上限，不是堆 OOM。",
         cause_en="Off-heap usage (netty/python/native) exceeded the YARN "
                  "container limit — distinct from a heap OOM.",
         fix_zh="调大 spark.executor.memoryOverhead（建议 executor 内存的 "
                "10%-20% 起步）；PySpark 任务检查 python 侧内存。",
         fix_en="Raise spark.executor.memoryOverhead (start at 10-20% of "
                "executor memory); for PySpark audit Python-side memory.",
         patch="spark-submit \\\n"
               "  --conf spark.executor.memoryOverhead=2g"),
    _sig("spark_fetch_failed", "spark", "error",
         r"FetchFailedException|Failed to connect to .*shuffle",
         title_zh="Shuffle 拉取失败",
         title_en="Shuffle fetch failure",
         cause_zh="上游 executor 挂掉或网络抖动导致 shuffle 块丢失，常由内存被杀连带引发。",
         cause_en="Upstream executor death or network flaps lost shuffle "
                  "blocks — often secondary to memory kills.",
         fix_zh="先修复日志里更早的 executor 失联/OOM 根因；可调大 "
                "spark.shuffle.io.maxRetries 与 retryWait 增强容错。",
         fix_en="Fix the earlier executor-loss/OOM root cause first; raise "
                "spark.shuffle.io.maxRetries / retryWait for resilience.",
         patch="spark-submit \\\n"
               "  --conf spark.shuffle.io.maxRetries=10 \\\n"
               "  --conf spark.shuffle.io.retryWait=15s"),
    _sig("spark_executor_lost", "spark", "error",
         r"ExecutorLostFailure|Lost executor \d+",
         title_zh="Executor 失联",
         title_en="Executor lost",
         cause_zh="executor 进程异常退出：内存被杀、节点故障或抢占。",
         cause_en="Executor process died: memory kill, node failure or "
                  "preemption.",
         fix_zh="查看该 executor 所在 NodeManager 日志确认退出原因；若为内存问题参照"
                "内存类修复项。",
         fix_en="Check the NodeManager log on that host for the exit reason; "
                "if memory-related, apply the memory fixes."),
    _sig("spark_task_not_serializable", "spark", "error",
         r"Task not serializable|NotSerializableException",
         title_zh="闭包不可序列化",
         title_en="Task not serializable",
         cause_zh="算子闭包引用了不可序列化对象（连接、客户端、外部类成员）。",
         cause_en="The operator closure captured a non-serializable object "
                  "(connection, client, outer-class member).",
         fix_zh="把连接/客户端移入 mapPartitions 内创建，或将成员标记 transient、"
                "改为局部变量。",
         fix_en="Create connections inside mapPartitions, or mark fields "
                "transient / use local variables."),
    _sig("spark_kryo_overflow", "spark", "error",
         r"KryoException.*Buffer overflow|kryoserializer\.buffer",
         title_zh="Kryo 序列化缓冲区溢出",
         title_en="Kryo serialization buffer overflow",
         cause_zh="单条记录序列化后超过 kryo 缓冲上限。",
         cause_en="A single record serialized larger than the kryo buffer cap.",
         fix_zh="调大 spark.kryoserializer.buffer.max（如 512m/1g）。",
         fix_en="Raise spark.kryoserializer.buffer.max (e.g. 512m/1g).",
         patch="spark-submit \\\n"
               "  --conf spark.kryoserializer.buffer.max=1g"),
    # ----------------------------------------------------------------- hive
    _sig("hive_metastore_conn", "hive", "critical",
         r"Could not connect to meta store|MetaException|"
         r"metastore.*Connection refused|TTransportException.*9083",
         title_zh="Metastore 连接失败",
         title_en="Hive metastore connection failure",
         cause_zh="metastore 服务不可达：进程挂了、端口（默认 9083）不通或地址配置错误。",
         cause_en="Metastore unreachable: service down, port 9083 blocked, or "
                  "a wrong hive.metastore.uris.",
         fix_zh="确认 metastore 进程与端口存活（telnet host 9083）；核对 "
                "hive.metastore.uris；查看 metastore 自身日志。",
         fix_en="Verify the metastore process/port (telnet host 9083); check "
                "hive.metastore.uris; inspect the metastore's own log.",
         patch="# confirm the metastore is reachable from the job's host\n"
               "telnet <metastore-host> 9083\n"
               "# check the configured address\n"
               "grep -A1 hive.metastore.uris hive-site.xml"),
    _sig("hive_semantic", "hive", "error",
         r"SemanticException",
         title_zh="HQL 语义错误",
         title_en="HiveQL semantic error",
         cause_zh="SQL 引用了不存在的表/列/分区，或语法与当前 Hive 版本不兼容。",
         cause_en="The SQL references a missing table/column/partition or "
                  "uses syntax incompatible with this Hive version.",
         fix_zh="按报错中的对象名核对库表结构（show create table）；上游表结构变更时"
                "同步修改 SQL。",
         fix_en="Check the named object against the schema (show create "
                "table); update the SQL after upstream schema changes."),
    _sig("hive_dynamic_partitions", "hive", "error",
         r"exceeds? (?:the )?max(?:imum)? (?:number of )?dynamic partitions|"
         r"Fatal error occurred when node tried to create too many dynamic partitions",
         title_zh="动态分区数超限",
         title_en="Too many dynamic partitions",
         cause_zh="单次写入产生的动态分区数超过 hive.exec.max.dynamic.partitions。",
         cause_en="One write produced more dynamic partitions than "
                  "hive.exec.max.dynamic.partitions allows.",
         fix_zh="确认分区键是否选错（高基数列误作分区）；确需超限时调大 "
                "hive.exec.max.dynamic.partitions(.pernode)。",
         fix_en="Verify the partition key isn't a high-cardinality column by "
                "mistake; otherwise raise hive.exec.max.dynamic.partitions(.pernode).",
         patch="SET hive.exec.dynamic.partition.mode=nonstrict;\n"
               "SET hive.exec.max.dynamic.partitions=5000;\n"
               "SET hive.exec.max.dynamic.partitions.pernode=1000;"),
    _sig("hive_tez_vertex", "hive", "error",
         r"Vertex failed|Vertex did not succeed",
         title_zh="Tez Vertex 失败",
         title_en="Tez vertex failure",
         cause_zh="Tez 任务某个 vertex 的 task 全部失败，真实原因在其 task 日志里。",
         cause_en="All attempts of one Tez vertex failed; the real cause is "
                  "in that vertex's task log.",
         fix_zh="用 yarn logs -applicationId <id> 拉取对应 task 日志，按其中的"
                "首个异常继续定位。",
         fix_en="Pull the task log via yarn logs -applicationId <id> and "
                "follow the first exception there.",
         patch="yarn logs -applicationId <application_id> | grep -B2 -A20 "
               "'Caused by'"),
    # ------------------------------------------------------------ seatunnel
    _sig("st_config_parse", "seatunnel", "critical",
         r"com\.typesafe\.config\.ConfigException|ConfigException\.(Parse|Missing|WrongType)",
         title_zh="SeaTunnel 配置解析失败",
         title_en="SeaTunnel config parse failure",
         cause_zh="HOCON 配置语法错误、缺少必填项或类型不符。",
         cause_en="HOCON syntax error, a missing required key, or a wrong "
                  "value type.",
         fix_zh="按报错给出的行号/键名修配置；用平台的 Config Lint（/configlint）"
                "先静态校验再提交。",
         fix_en="Fix the line/key named in the error; pre-validate with the "
                "Config Lint agent (/configlint) before submitting."),
    _sig("st_plugin_not_found", "seatunnel", "critical",
         r"PluginIdentifier|Plugin.*not (?:found|exist)|"
         r"Can(?:no|')t find .*(?:connector|plugin)",
         title_zh="连接器插件未找到",
         title_en="Connector plugin not found",
         cause_zh="配置里的 connector 名拼写错误，或对应插件 jar 未安装到 "
                  "connectors 目录。",
         cause_en="The connector name is misspelled, or its jar is not "
                  "installed under the connectors directory.",
         fix_zh="核对 source/sink 的 plugin 名大小写；执行 install-plugin 或把"
                "连接器 jar 放入 connectors/ 后重启。",
         fix_en="Check the source/sink plugin name casing; run install-plugin "
                "or drop the connector jar into connectors/ and restart.",
         patch="# install the missing connector (name from the error)\n"
               "sh bin/install-plugin.sh\n"
               "# or drop the jar manually, then restart\n"
               "cp seatunnel-connectors-<name>-<version>.jar connectors/"),
    _sig("st_type_mismatch", "seatunnel", "error",
         r"UnsupportedTypeException|Unsupported.*data type|"
         r"CatalogException.*type|DataTypeConvertException",
         title_zh="字段类型不支持/不匹配",
         title_en="Unsupported or mismatched column type",
         cause_zh="源端字段类型超出连接器支持范围，或 schema 声明与实际数据不符。",
         cause_en="A source column type is outside what the connector "
                  "supports, or the declared schema mismatches the data.",
         fix_zh="在 source 侧 cast 成受支持类型，或在 transform 中显式转换；"
                "核对 schema 配置与真实表结构。",
         fix_en="Cast to a supported type at the source or in a transform; "
                "reconcile the schema block with the real table."),
    _sig("st_checkpoint_timeout", "seatunnel", "error",
         r"checkpoint.*(?:timeout|expired)|CheckpointCoordinator.*fail",
         title_zh="Checkpoint 超时/失败",
         title_en="Checkpoint timeout/failure",
         cause_zh="反压或 sink 写入过慢导致 checkpoint 无法在超时内完成。",
         cause_en="Backpressure or a slow sink kept the checkpoint from "
                  "completing in time.",
         fix_zh="调大 checkpoint.timeout；定位慢的 sink（批大小、并发、目标库"
                "写入能力）；必要时降低 source 速率。",
         fix_en="Raise checkpoint.timeout; profile the slow sink (batch size, "
                "parallelism, target write capacity); throttle the source.",
         patch="env {\n"
               "  checkpoint.interval = 60000\n"
               "  checkpoint.timeout = 120000\n"
               "}"),
    # -------------------------------------------- generic / hadoop / jdbc
    _sig("gen_class_not_found", "generic", "error",
         r"ClassNotFoundException|NoClassDefFoundError",
         title_zh="类缺失（依赖未上车）",
         title_en="Missing class (dependency not on classpath)",
         cause_zh="运行时 classpath 缺少依赖 jar，或依赖版本冲突被错误 shade。",
         cause_en="A required jar is absent from the runtime classpath, or a "
                  "version conflict shaded it away.",
         fix_zh="把缺失类所在 jar 通过 --jars / connectors 目录 / aux jars 带上；"
                "版本冲突时统一依赖版本。",
         fix_en="Ship the jar via --jars / connectors dir / aux jars; align "
                "dependency versions on conflicts."),
    _sig("gen_hdfs_quota", "generic", "critical",
         r"DSQuotaExceededException|NSQuotaExceededException|QuotaExceededException",
         title_zh="HDFS 配额超限",
         title_en="HDFS quota exceeded",
         cause_zh="目标目录的空间或文件数配额用尽，写入被 NameNode 拒绝。",
         cause_en="The target directory's space or namespace quota is spent; "
                  "the NameNode rejects writes.",
         fix_zh="清理过期数据/小文件，或找管理员调整配额（hdfs dfsadmin -setSpaceQuota）。",
         fix_en="Purge stale data/small files, or have an admin raise the "
                "quota (hdfs dfsadmin -setSpaceQuota).",
         patch="# inspect the quota and usage of the rejected directory\n"
               "hdfs dfs -count -q -h /path/to/dir\n"
               "# admin: raise the space quota\n"
               "hdfs dfsadmin -setSpaceQuota 10t /path/to/dir"),
    _sig("gen_no_space", "generic", "critical",
         r"No space left on device",
         title_zh="本地磁盘写满",
         title_en="Local disk full",
         cause_zh="节点本地盘（shuffle/tmp/日志目录）没有剩余空间。",
         cause_en="A node's local disk (shuffle/tmp/log dir) ran out of space.",
         fix_zh="清理该节点临时目录；为 shuffle 配置多块盘；给日志配置滚动清理。",
         fix_en="Clean the node's tmp dirs; spread shuffle across disks; add "
                "log rotation."),
    _sig("gen_hdfs_permission", "generic", "error",
         r"AccessControlException|Permission denied",
         title_zh="权限不足",
         title_en="Permission denied",
         cause_zh="任务运行账号对目标路径/表没有读写权限。",
         cause_en="The job's user lacks read/write permission on the target "
                  "path or table.",
         fix_zh="确认任务以哪个账号提交；用 hdfs dfs -ls 查看目录属主与权限，"
                "按最小权限原则授权。",
         fix_en="Confirm the submitting user; inspect ownership with hdfs dfs "
                "-ls and grant least-privilege access.",
         patch="# who owns the path, and with what mode?\n"
               "hdfs dfs -ls -d /path/from/the/error\n"
               "# grant the job user access (least privilege)\n"
               "hdfs dfs -setfacl -m user:<job_user>:rwx /path/from/the/error"),
    _sig("gen_kerberos", "generic", "critical",
         r"GSSException|Kerberos|SASL.*(?:fail|error)|TGT",
         title_zh="Kerberos 认证失败",
         title_en="Kerberos authentication failure",
         cause_zh="票据过期、keytab 不对或 principal 配置错误。",
         cause_en="Expired ticket, a wrong keytab, or a misconfigured "
                  "principal.",
         fix_zh="kinit 重新获取票据；核对 keytab 与 principal；长任务配置自动续票。",
         fix_en="Re-kinit; verify keytab and principal; configure ticket "
                "renewal for long jobs.",
         patch="# renew the ticket with the job's keytab\n"
               "kinit -kt /path/to/job.keytab <principal>@<REALM>\n"
               "klist   # verify expiry"),
    _sig("gen_jdbc_refused", "generic", "error",
         r"Connection refused|CommunicationsException|"
         r"Could not open client transport|connect timed out",
         title_zh="下游服务连接失败",
         title_en="Downstream connection failure",
         cause_zh="目标库/服务不可达：地址端口写错、服务未启动或网络/防火墙阻断。",
         cause_en="Target DB/service unreachable: wrong host/port, service "
                  "down, or network/firewall block.",
         fix_zh="在任务运行的节点上 telnet 目标端口验证连通性；核对 url；确认服务"
                "与白名单。",
         fix_en="Telnet the target port from the job's node; verify the URL; "
                "check the service and allowlists."),
    _sig("gen_jdbc_auth", "generic", "error",
         r"Access denied for user|password authentication failed|"
         r"invalid username/password",
         title_zh="数据库认证失败",
         title_en="Database authentication failure",
         cause_zh="用户名/密码错误，或账号没有从任务所在网段登录的权限。",
         cause_en="Wrong username/password, or the account cannot log in from "
                  "the job's network segment.",
         fix_zh="核对凭据与账号的 host 维度授权（MySQL 的 user@host）；密码轮换后"
                "同步更新任务配置。",
         fix_en="Verify credentials and host-scoped grants (user@host in "
                "MySQL); sync rotated passwords into the job config."),
    _sig("gen_unknown_host", "generic", "error",
         r"UnknownHostException",
         title_zh="主机名无法解析",
         title_en="Unknown host",
         cause_zh="DNS/hosts 缺少目标主机名解析，常见于容器内未挂载集群 hosts。",
         cause_en="DNS/hosts cannot resolve the hostname — common when a "
                  "container lacks the cluster hosts mapping.",
         fix_zh="为运行环境补全 hosts 或 DNS；或在配置中改用 IP/FQDN。",
         fix_en="Add the hosts/DNS entries to the runtime, or switch the "
                "config to an IP/FQDN."),
)

# engine detection: package markers scored over the whole scanned text
ENGINE_MARKERS: tuple[tuple[str, re.Pattern], ...] = (
    ("seatunnel", re.compile(r"org\.apache\.seatunnel|seatunnel", re.I)),
    ("spark", re.compile(r"org\.apache\.spark|SparkContext|spark-submit", re.I)),
    ("hive", re.compile(r"org\.apache\.h(?:ive|adoop\.hive)|HiveServer2|"
                        r"metastore|SemanticException|Tez", re.I)),
)
