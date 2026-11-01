"""Data Skew agent: syntax-level skew detection + LLM SQL rewrite.

Supports Spark SQL (Spark 3) and MaxCompute SQL (Hive accepted as a
compatible input dialect). Pure static analysis — the SQL is never
executed and no data source connection is required.
"""

from .agent import (
    DataSkewAgent,
    SkewAnalysisResult,
    static_skew_check,
    static_skew_report,
)
from .bench import DEFAULT_CORPUS, load_corpus, render_bench, run_bench
from .consistency import (
    check_consistency,
    extract_single_select,
    render_consistency_section,
)
from .detector import (
    DIALECTS,
    RULE_TEXTS,
    detect_skew,
    normalize_dialect,
    split_statements,
)
from .drift import drift_for, drift_item_dict, notify_decision, render_drift
from .history import default_history
from .i18n import dsk
from .mcp_server import build_tool_functions, create_mcp_server
from .notify import post_webhook
from .probe import (
    effective_sample_pct,
    extract_probe_targets,
    render_probe_section,
    run_probes,
)
from .report import Severity, SkewFinding, SkewReport, render_report
from .runtime import (
    RuntimeSkewError,
    analyze_flink,
    analyze_history_server,
    diagnose_and_log,
    parse_eventlog,
)
from .shuffle_dist import (
    render_salt_what_if,
    render_shuffle_dist,
    salt_what_if,
    shuffle_distribution,
)
from .splitkey import (
    SplitKeyError,
    apply_split_key,
    batch_counts,
    pick_best_key,
    render_splitkey_batch,
    render_splitkey_multi,
    run_split_key_batch,
    run_split_key_multi,
    scan_config_files,
    sink_key_section,
    splitkey_metrics,
)

# Everything another agent or entry point needs lives on this facade —
# cross-package imports of data_skew submodules are a seam leak.
__all__ = [
    "DEFAULT_CORPUS",
    "DIALECTS",
    "DataSkewAgent",
    "RULE_TEXTS",
    "RuntimeSkewError",
    "Severity",
    "SkewAnalysisResult",
    "SkewFinding",
    "SkewReport",
    "SplitKeyError",
    "analyze_flink",
    "analyze_history_server",
    "apply_split_key",
    "batch_counts",
    "build_tool_functions",
    "check_consistency",
    "create_mcp_server",
    "default_history",
    "detect_skew",
    "diagnose_and_log",
    "drift_for",
    "drift_item_dict",
    "dsk",
    "effective_sample_pct",
    "extract_probe_targets",
    "extract_single_select",
    "load_corpus",
    "normalize_dialect",
    "notify_decision",
    "parse_eventlog",
    "pick_best_key",
    "post_webhook",
    "render_bench",
    "render_consistency_section",
    "render_drift",
    "render_probe_section",
    "render_report",
    "render_salt_what_if",
    "render_shuffle_dist",
    "render_splitkey_batch",
    "render_splitkey_multi",
    "run_bench",
    "run_probes",
    "run_split_key_batch",
    "run_split_key_multi",
    "salt_what_if",
    "scan_config_files",
    "shuffle_distribution",
    "sink_key_section",
    "split_statements",
    "splitkey_metrics",
    "static_skew_check",
    "static_skew_report",
]
