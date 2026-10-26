"""One-command Chat BI demo environment.

Generates a self-contained playground under a target directory — a sqlite
sales database with recognizable structure (weekday pattern, a refund
anomaly, holiday lift), a metrics.yaml exercising every semantic-layer
feature (ratio, tree, targets, aliases), the matching DDL whitelist and a
question list — so a reviewer goes from zero to asking "春节期间的 GMV"
in thirty seconds. Deterministic (seeded) and offline.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from . import calendar_cn

_CHANNELS = {"app": 1.0, "web": 0.6, "mini": 0.3}
_PROVINCES = ["广东", "浙江", "江苏", "四川"]

_DDL = """CREATE TABLE sales (
  order_id string COMMENT '订单ID',
  pay_amount double COMMENT '应付金额',
  refund_amount double COMMENT '退款金额',
  channel string COMMENT '渠道',
  province string COMMENT '省份',
  dt string COMMENT '日期'
) COMMENT '销售明细(演示数据)';
"""

_METRICS = """metrics:
  - name: gmv
    display_name: GMV
    aliases: [成交总额, 交易额]
    description: 已支付订单的应付金额合计
    table: sales
    expression: SUM(pay_amount)
    time_column: dt
    dimensions: [channel, province]
    unit: 元
    targets: {month: 400000}
    tree: [order_cnt, aov]
  - name: order_cnt
    display_name: 订单量
    aliases: [单量]
    table: sales
    expression: COUNT(order_id)
    time_column: dt
    dimensions: [channel, province]
  - name: aov
    display_name: 客单价
    type: ratio
    numerator: gmv
    denominator: order_cnt
  - name: refund_amount
    display_name: 退款额
    table: sales
    expression: SUM(refund_amount)
    time_column: dt
    dimensions: [channel, province]
    unit: 元
  - name: refund_rate
    display_name: 退款率
    aliases: [退款占比]
    type: ratio
    numerator: refund_amount
    denominator: gmv
"""

_QUESTIONS = """# 可以问的 10 个问题(演示路径)

1. 昨天各渠道的销售额 —— 指标命中,确定性 SQL
2. GMV 的口径是什么 —— 纯问答,不执行 SQL
3. 上周销售额为什么跌了 —— 因子树分解(单量还是客单价)+ 维度归因
4. 春节期间的 GMV —— 中文业务时间,官方节假日区间
5. 预测未来 7 天 GMV —— 趋势+星期季节性+节假日偏移,95% 区间
6. 本月 GMV 达成率多少,月底能完成吗 —— 目标进度 + 期末投影
7. 退款率和 GMV 相关吗 —— Pearson + 领先/滞后扫描
8. 退款率最近有没有异常 —— {anomaly_day} 有一次人造退款尖峰
9. 近30天各省份订单量 —— 相对时间词 + 维度下钻
10. 这个数是从哪些表算出来的 —— 指标溯源

## 订阅演示(可选,会写入当前目录的订阅文件)

seatunnel-agent t2s-sub add --name 经营日报 --cron "0 9 * * *" \\
    --digest "gmv,order_cnt,refund_rate" --ds-type sqlite --database {db}
seatunnel-agent t2s-sub add --name GMV异动 --cron "30 8 * * *" \\
    --metric gmv --watch --watch-mode model --ds-type sqlite --database {db}
seatunnel-agent t2s-sub backtest <订阅ID> --days 30
"""


def build_demo(target_dir: str | Path, days: int = 60) -> dict:
    """Generate the demo assets; returns paths and headline facts."""
    out = Path(target_dir)
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / "demo.db"
    rng = random.Random(42)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    anomaly_day = end - timedelta(days=10)

    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS sales")
    conn.execute(
        "CREATE TABLE sales(order_id TEXT, pay_amount REAL, "
        "refund_amount REAL, channel TEXT, province TEXT, dt TEXT)"
    )
    rows = []
    oid = 0
    d = start
    while d <= end:
        weekday_lift = 0.7 if d.weekday() >= 5 else 1.0
        holiday_lift = 1.4 if calendar_cn.is_holiday(d) else 1.0
        for channel, weight in _CHANNELS.items():
            n_orders = max(1, round(20 * weight * weekday_lift * holiday_lift))
            for _ in range(n_orders):
                oid += 1
                amount = round(rng.uniform(80, 320) * holiday_lift, 2)
                refund_share = 0.05 if d != anomaly_day else 0.18
                refund = (
                    round(amount * rng.uniform(0.5, 1.5) * refund_share, 2)
                    if rng.random() < 0.3 else 0.0
                )
                rows.append((
                    f"o{oid:06d}", amount, refund, channel,
                    rng.choice(_PROVINCES), d.isoformat(),
                ))
        d += timedelta(days=1)
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    (out / "schema_ddl.sql").write_text(_DDL, encoding="utf-8")
    (out / "metrics.yaml").write_text(_METRICS, encoding="utf-8")
    (out / "QUESTIONS.md").write_text(
        _QUESTIONS.format(db=db_path, anomaly_day=anomaly_day.isoformat()),
        encoding="utf-8",
    )
    return {
        "dir": str(out),
        "db": str(db_path),
        "ddl": str(out / "schema_ddl.sql"),
        "metrics": str(out / "metrics.yaml"),
        "questions": str(out / "QUESTIONS.md"),
        "rows": len(rows),
        "days": days,
        "anomaly_day": anomaly_day.isoformat(),
    }
