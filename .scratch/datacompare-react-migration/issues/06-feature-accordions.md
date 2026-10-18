# 06: Feature accordions — incremental / quality / skew / checksum / partition / custom agg / custom SQL

**What to build:** The seven analysis accordions work 1:1: incremental watermark compare, quality rules, skew analysis, checksum incl. chunked, partition compare, custom aggregates, custom SQL A/B — each rendering its legacy-equivalent card.

**Blocked by:** 03 — Core actions, 05 — Options + presets

**Status:** done

- [x] Each accordion action renders its card with options applied
- [x] In-process API tests for at least checksum (incl. chunked) and custom SQL contracts
- [x] Project verification commands green
