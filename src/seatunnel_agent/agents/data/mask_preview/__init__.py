"""脱敏预览 — 真实数据行 → 敏感列判定 + 保格式脱敏样例.

Deterministic core: parse the pasted rows (sample_profile's parser
reused), detect sensitive columns by name (pii_scan's rule catalog
reused) and by value shape (CN phone / ID card / email / bank card),
apply format-preserving value masks, and show the rows before and
after.  pii_scan plans SQL-level masking from DDL and lineage; this
masks the data itself.  Nothing leaves the process.
"""

from .masker import (
    ColumnMask,
    MaskPreview,
    detect_category,
    mask_value,
    preview_mask,
)
from .report import render_markdown

__all__ = [
    "ColumnMask",
    "MaskPreview",
    "detect_category",
    "mask_value",
    "preview_mask",
    "render_markdown",
]
