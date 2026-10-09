# 全库同步生成器 Demo

`mysql_schema.sql` 模拟一个业务库 `shop` 的 DDL 快照：6 张表覆盖类型矩阵
（unsigned / decimal / enum / json / bit / geometry）、PII 列（手机号/身份证/
地址，中文注释命中）、无主键表、以及 `*_tmp` / `*_bak` 过滤演示表。

## 三条演示命令

```bash
# 1. 零配置 dry-run：console sink，只看 manifest
seatunnel-agent syncgen --ddl examples/sync_gen_demo/mysql_schema.sql --dry-run

# 2. 完整生成：StarRocks 目标端 + PII 脱敏 + 排除临时/备份表
seatunnel-agent syncgen --ddl examples/sync_gen_demo/mysql_schema.sql \
    --sink-type starrocks --pii --exclude '.*_(tmp|bak)$' \
    --out out/sync_demo --lang zh

# 3. CI 门禁：发现 PII 列但未开 --pii 时退出 1（"不许上线未脱敏同步任务"）
seatunnel-agent syncgen --ddl examples/sync_gen_demo/mysql_schema.sql \
    --dry-run --fail-on pii
```

产物布局（命令 2）：

```
out/sync_demo/
  configs/shop__users.conf     # 每张表一个 SeaTunnel 配置（${var} 占位符，无真实凭据）
  ddl/shop__users.sql          # 目标端建表语句（类型已映射，enum 取值写进 COMMENT）
  manifest.json                # 机器可读清单
  manifest.md                  # 人类可读报告（PII 列、警告、跳过的表）
```

`extra_pii_rules.yaml` 演示自定义 PII 规则（`--pii-rules` 追加到内置目录）。

在线模式（需要可访问的 MySQL）：

```bash
export MYSQL_HOST=... MYSQL_PORT=3306 MYSQL_USERNAME=... MYSQL_PASSWORD=...
seatunnel-agent syncgen --db shop --sink-type doris --pii --out out/shop
```
