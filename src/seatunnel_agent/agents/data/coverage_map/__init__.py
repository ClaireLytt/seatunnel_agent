"""质量覆盖地图 — DDL × DQC 规则/契约 → 逐表防护与裸奔点名.

Deterministic core: parse the DDL (schema_drift reused), the DQC rules
(data_quality's parser reused) and the contract (contract_check's
parser reused), then map every table's gates — unguarded tables graded
(high in the hot dwd/dws/ads layers), gates naming absent tables
flagged as dead, the coverage share up front.  dq_rulegen and
contract_gen draft what is missing.  No database connection.
"""

from .mapper import CoverageFinding, CoverageMap, TableCoverage, map_coverage
from .report import render_markdown

__all__ = [
    "CoverageFinding",
    "CoverageMap",
    "TableCoverage",
    "map_coverage",
    "render_markdown",
]
