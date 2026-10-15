"""Full-chain data lineage agent: table/column lineage across SQL files
and the Hive metadata lineage table (zz.dwm_meta_table_lineage_df).

Answers questions like "这个表的上下游是什么" and "改这个字段影响哪些下游表",
with SLA/baseline flags surfaced along the chain.
"""

from .agent import LineageAgent, static_lineage
from .config import DEFAULT_META_TABLE, LineageConfig, load_lineage_config
from .graph import (
    ChainResult,
    ColumnEdge,
    ColumnImpactResult,
    HealthReport,
    LineageGraph,
    SlaImpactResult,
    TableNode,
    norm_table,
)
from .loaders import build_graph, from_hive_meta, from_sql_dir, from_sql_files
from .seatunnel_loader import from_seatunnel_dir, from_seatunnel_files
from .render import (
    mermaid_html,
    render_column_mermaid,
    render_health,
    render_mermaid,
    render_path,
    render_path_mermaid,
    render_report,
    render_sla_impact,
    render_tree,
)
from .report import LineageReport
from .rlog import LineageLogger

__all__ = [
    "LineageAgent",
    "static_lineage",
    "LineageGraph",
    "TableNode",
    "ColumnEdge",
    "ChainResult",
    "ColumnImpactResult",
    "SlaImpactResult",
    "HealthReport",
    "norm_table",
    "LineageConfig",
    "load_lineage_config",
    "DEFAULT_META_TABLE",
    "build_graph",
    "from_sql_dir",
    "from_sql_files",
    "from_hive_meta",
    "from_seatunnel_dir",
    "from_seatunnel_files",
    "LineageReport",
    "render_report",
    "render_mermaid",
    "render_column_mermaid",
    "render_tree",
    "render_path",
    "render_path_mermaid",
    "render_sla_impact",
    "render_health",
    "mermaid_html",
    "LineageLogger",
]
