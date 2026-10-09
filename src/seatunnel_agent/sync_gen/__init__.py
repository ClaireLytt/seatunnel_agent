# -*- coding: utf-8 -*-
"""全库同步生成器 (whole-database sync generator).

Introspect a source MySQL database (live) or parse offline DDL files,
then batch-generate one SeaTunnel HOCON sync config per table, the
target-side CREATE TABLE DDL (Doris / StarRocks / Hive type mapping),
optional PII masking transforms, and a summary manifest.

Deterministic — no LLM; live DB used only to *read* schemas. Deferred:
live-DB over REST/UI, Hive partitioned DDL, per-column mask overrides,
CDC/STREAMING mode, plugin_input/plugin_output naming toggle, live-mode
primary-key discovery, UI zip download.
"""

from .core import SyncPlan, SyncResult, generate_sync, write_outputs
from .report import render_markdown, report_to_dict

__all__ = ["SyncPlan", "SyncResult", "generate_sync", "write_outputs",
           "render_markdown", "report_to_dict"]
