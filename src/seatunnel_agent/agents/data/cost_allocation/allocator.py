"""Deterministic cost allocation over a resource-usage inventory.

storage_cost prices what the warehouse holds and retention_policy says
what to keep; this agent answers the question finance actually asks:
**who pays**.  Paste a usage inventory — columns ``owner`` (team or
business line, empty = unallocated), ``item`` (table or job),
``storage_gb``, ``compute_hours`` — plus unit prices, and the bill
comes back per owner with each team's top cost drivers:

* CA001 — unallocated spend (no owner): medium from 10% of the total,
  high from 30% — nobody optimizes a cost nobody owns;
* CA002 low — one owner carries over half the bill: concentration
  worth a look before the next budget round.

Same inventory + prices = same bill.  No billing-system connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["CostBill", "CostFinding", "OwnerBill", "allocate_costs"]

_UNALLOC_MED = 0.10
_UNALLOC_HIGH = 0.30
_CONCENTRATION = 0.50
_TOP_ITEMS = 3
_UNALLOCATED = "(unallocated)"


@dataclass
class OwnerBill:
    owner: str
    items: int = 0
    storage_gb: float = 0.0
    compute_hours: float = 0.0
    storage_cost: float = 0.0
    compute_cost: float = 0.0
    top_items: list[tuple[str, float]] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.storage_cost + self.compute_cost

    def to_dict(self) -> dict[str, Any]:
        return {"owner": self.owner, "items": self.items,
                "storage_gb": round(self.storage_gb, 2),
                "compute_hours": round(self.compute_hours, 2),
                "storage_cost": round(self.storage_cost, 2),
                "compute_cost": round(self.compute_cost, 2),
                "total": round(self.total, 2),
                "top_items": [{"item": n, "cost": round(c, 2)}
                              for n, c in self.top_items]}


@dataclass
class CostFinding:
    code: str            # CA001 | CA002
    severity: str        # high | medium | low
    owner: str
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "owner": self.owner, "value": round(self.value, 4)}


@dataclass
class CostBill:
    storage_price: float
    compute_price: float
    owners: list[OwnerBill] = field(default_factory=list)
    findings: list[CostFinding] = field(default_factory=list)
    total: float = 0.0
    unallocated_share: float = 0.0

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"storage_price": self.storage_price,
                "compute_price": self.compute_price,
                "total": round(self.total, 2),
                "unallocated_share": round(self.unallocated_share, 4),
                "counts": self.counts(),
                "owners": [o.to_dict() for o in self.owners],
                "findings": [f.to_dict() for f in self.findings]}


def allocate_costs(headers: list[str], rows: list[dict[str, str | None]],
                   storage_price: float = 0.02,
                   compute_price: float = 0.5) -> CostBill:
    """Usage inventory + unit prices → per-owner bill, biggest first."""
    needed = {"owner", "item", "storage_gb", "compute_hours"}
    missing = needed - {h.lower() for h in headers}
    if missing:
        raise ValueError("inventory needs columns owner/item/storage_gb/"
                         f"compute_hours — missing: "
                         f"{', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("the inventory has no rows")
    if storage_price < 0 or compute_price < 0:
        raise ValueError("unit prices must not be negative")
    col = {h.lower(): h for h in headers}

    bill = CostBill(storage_price=storage_price,
                    compute_price=compute_price)
    by_owner: dict[str, OwnerBill] = {}
    item_costs: dict[str, list[tuple[str, float]]] = {}
    for i, r in enumerate(rows):
        owner = str(r.get(col["owner"]) or "").strip() or _UNALLOCATED
        item = str(r.get(col["item"]) or "").strip()
        if not item:
            raise ValueError(f"row {i + 1}: item is required")
        try:
            gb = float(r.get(col["storage_gb"]) or 0)
            hours = float(r.get(col["compute_hours"]) or 0)
        except ValueError:
            raise ValueError(f"row {i + 1}: storage_gb and compute_hours "
                             "must be numbers")
        if gb < 0 or hours < 0:
            raise ValueError(f"row {i + 1}: usage must not be negative")
        ob = by_owner.setdefault(owner, OwnerBill(owner=owner))
        ob.items += 1
        ob.storage_gb += gb
        ob.compute_hours += hours
        ob.storage_cost += gb * storage_price
        ob.compute_cost += hours * compute_price
        cost = gb * storage_price + hours * compute_price
        item_costs.setdefault(owner, []).append((item, cost))

    for owner, ob in by_owner.items():
        ob.top_items = sorted(item_costs[owner],
                              key=lambda kv: -kv[1])[:_TOP_ITEMS]
        bill.total += ob.total
    bill.owners = sorted(by_owner.values(), key=lambda o: -o.total)

    unalloc = by_owner.get(_UNALLOCATED)
    if unalloc and bill.total:
        bill.unallocated_share = unalloc.total / bill.total
        if bill.unallocated_share >= _UNALLOC_MED:
            bill.findings.append(CostFinding(
                code="CA001",
                severity="high" if bill.unallocated_share >= _UNALLOC_HIGH
                else "medium",
                owner=_UNALLOCATED, value=bill.unallocated_share))
    if bill.total and bill.owners:
        top = bill.owners[0]
        if (top.owner != _UNALLOCATED
                and top.total / bill.total >= _CONCENTRATION):
            bill.findings.append(CostFinding(
                code="CA002", severity="low", owner=top.owner,
                value=top.total / bill.total))
    return bill
