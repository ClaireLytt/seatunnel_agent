"""SQL query template library — preset analytical patterns."""

from __future__ import annotations

from typing import Any


SQL_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "mom",
        "name_en": "Month-over-Month",
        "name_zh": "环比分析",
        "description_en": "Compare a metric between the current and previous month",
        "description_zh": "对比当月与上月的指标变化",
        "pattern": (
            "SELECT curr.{dim}, curr.{metric} AS current_month,\n"
            "       prev.{metric} AS previous_month,\n"
            "       (curr.{metric} - prev.{metric}) / prev.{metric} * 100 AS mom_pct\n"
            "FROM (\n"
            "  SELECT {dim}, SUM({metric}) AS {metric}\n"
            "  FROM {table} WHERE {date_col} BETWEEN '{curr_start}' AND '{curr_end}'\n"
            "  GROUP BY {dim}\n"
            ") curr\n"
            "LEFT JOIN (\n"
            "  SELECT {dim}, SUM({metric}) AS {metric}\n"
            "  FROM {table} WHERE {date_col} BETWEEN '{prev_start}' AND '{prev_end}'\n"
            "  GROUP BY {dim}\n"
            ") prev ON curr.{dim} = prev.{dim}"
        ),
    },
    {
        "id": "yoy",
        "name_en": "Year-over-Year",
        "name_zh": "同比分析",
        "description_en": "Compare a metric between the current and same period last year",
        "description_zh": "对比今年与去年同期的指标变化",
        "pattern": (
            "SELECT curr.{dim}, curr.{metric} AS this_year,\n"
            "       prev.{metric} AS last_year,\n"
            "       (curr.{metric} - prev.{metric}) / prev.{metric} * 100 AS yoy_pct\n"
            "FROM (\n"
            "  SELECT {dim}, SUM({metric}) AS {metric}\n"
            "  FROM {table} WHERE YEAR({date_col}) = {year}\n"
            "  GROUP BY {dim}\n"
            ") curr\n"
            "LEFT JOIN (\n"
            "  SELECT {dim}, SUM({metric}) AS {metric}\n"
            "  FROM {table} WHERE YEAR({date_col}) = {year} - 1\n"
            "  GROUP BY {dim}\n"
            ") prev ON curr.{dim} = prev.{dim}"
        ),
    },
    {
        "id": "topn",
        "name_en": "Top N",
        "name_zh": "Top N 排行",
        "description_en": "Get the top N records by a metric",
        "description_zh": "按指标排名取前 N 条记录",
        "pattern": (
            "SELECT {dim}, {metric}\n"
            "FROM {table}\n"
            "ORDER BY {metric} DESC\n"
            "LIMIT {n}"
        ),
    },
    {
        "id": "ranked_groups",
        "name_en": "Ranked Groups",
        "name_zh": "分组排名",
        "description_en": "Rank records within each group using window functions",
        "description_zh": "使用窗口函数对分组内记录进行排名",
        "pattern": (
            "SELECT *, ROW_NUMBER() OVER(\n"
            "  PARTITION BY {group_col} ORDER BY {metric} DESC\n"
            ") AS rank\n"
            "FROM {table}"
        ),
    },
    {
        "id": "daily_trend",
        "name_en": "Daily Trend",
        "name_zh": "每日趋势",
        "description_en": "Show a metric's daily trend over a date range",
        "description_zh": "展示某个指标在日期范围内的每日趋势",
        "pattern": (
            "SELECT {date_col}, SUM({metric}) AS {metric}\n"
            "FROM {table}\n"
            "WHERE {date_col} BETWEEN '{start}' AND '{end}'\n"
            "GROUP BY {date_col}\n"
            "ORDER BY {date_col}"
        ),
    },
    {
        "id": "proportion",
        "name_en": "Proportion / Share",
        "name_zh": "占比分析",
        "description_en": "Calculate each group's proportion of the total",
        "description_zh": "计算每个分组占总量的比例",
        "pattern": (
            "SELECT {dim}, SUM({metric}) AS {metric},\n"
            "       SUM({metric}) / SUM(SUM({metric})) OVER() * 100 AS pct\n"
            "FROM {table}\n"
            "GROUP BY {dim}\n"
            "ORDER BY {metric} DESC"
        ),
    },
    {
        "id": "moving_avg",
        "name_en": "Moving Average",
        "name_zh": "移动平均",
        "description_en": "Compute a rolling N-day average of a metric",
        "description_zh": "计算某指标的 N 日滚动平均值",
        "pattern": (
            "SELECT {date_col}, {metric},\n"
            "       AVG({metric}) OVER(\n"
            "         ORDER BY {date_col} ROWS BETWEEN {n}-1 PRECEDING AND CURRENT ROW\n"
            "       ) AS moving_avg_{n}d\n"
            "FROM {table}\n"
            "ORDER BY {date_col}"
        ),
    },
    {
        "id": "cumulative_sum",
        "name_en": "Cumulative Sum",
        "name_zh": "累计求和",
        "description_en": "Compute a running total of a metric over time",
        "description_zh": "按时间顺序计算指标的累计值",
        "pattern": (
            "SELECT {date_col}, {metric},\n"
            "       SUM({metric}) OVER(\n"
            "         ORDER BY {date_col} ROWS UNBOUNDED PRECEDING\n"
            "       ) AS cumulative_{metric}\n"
            "FROM {table}\n"
            "ORDER BY {date_col}"
        ),
    },
]


def get_template(template_id: str) -> dict[str, Any] | None:
    for t in SQL_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def template_choices(lang: str = "en") -> list[str]:
    name_key = "name_zh" if lang == "zh" else "name_en"
    return [f"{t[name_key]} [{t['id']}]" for t in SQL_TEMPLATES]


def template_description(template_id: str, lang: str = "en") -> str:
    t = get_template(template_id)
    if t is None:
        return ""
    desc_key = "description_zh" if lang == "zh" else "description_en"
    return f"{t[desc_key]}\n\n```sql\n{t['pattern']}\n```"
