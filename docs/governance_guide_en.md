# Data Governance Guide (Hygiene · Metadata Quality · PII · Contract · Grants · Migration Guard)

The Chinese original is [governance_guide.md](governance_guide.md); this is its English mirror.

Six deterministic agents cover the governance loop — every one runs on static SQL
files with no database connection and no API key, so they fit a laptop and a PR
pipeline alike. Each ships four surfaces: a web page, a CLI subcommand with
`--fail-on` CI gates and `-F json`, a directory-whitelisted REST endpoint, and a
chat/MCP tool. Try them all on one directory: `examples/governance_demo/`.

## Find: Warehouse Hygiene (`/hygiene`)

```bash
seatunnel-agent hygiene --dir warehouse_sql/ --exempt exempt.yaml --fail-on orphans
```

Lineage-driven dead weight: write-only orphan tables, columns no downstream ever
selects, DDL definitions absent from any lineage edge. `exempt.yaml` lists
fnmatch patterns for tables external BI tools read directly.

## Regulate: Metadata Quality (`/metaquality`)

```bash
seatunnel-agent metaquality --dir warehouse_sql/ --fail-on high
```

DDL conventions: per-table comment coverage, cross-layer naming mismatches (an
`ods_` table living in `dwd`), type anti-patterns (money on FLOAT high, money or
dates on bare STRING medium), unpartitioned `dwd`/`dws` fact tables, and missing
owner/team in TBLPROPERTIES on modelled layers.

## Promise: Data Contract (`/contract`)

```bash
seatunnel-agent contract -d warehouse_sql/ -c contract.yaml --fail-on high
seatunnel-agent contract --init -d warehouse_sql/ -o contract.yaml   # bootstrap
```

Declared YAML promises vs actual DDL: missing tables/columns and type
mismatches are high, partition violations medium, comment requirements and
columns outside the contract low. `--init` generates the draft from current
DDL — it round-trips clean, so trim it and check it in.

## Protect: PII Scan (`/pii`)

See [pii_guide.md](pii_guide.md): naming rules × column lineage find sensitive
columns and unmasked downstream spread; `--mask` generates executable masked-view
DDL, and the gate becomes treatment-aware (only uncovered findings fail CI).

## Close off: Grant Surface (`/grants`)

```bash
seatunnel-agent grants --dir warehouse_sql/ --fail-on high
```

Parses GRANT/REVOKE, nets same-key revokes, grades the surviving surface:
grants to PUBLIC high, grants on PII-flagged tables high (linked to the PII
scanner over the same script), ALL PRIVILEGES and database-wide scopes medium.

## Escort: Migration Guard (`/ddlguard`)

```bash
seatunnel-agent ddlguard -f migrate.sql --fail-on high -u undo.sql
```

Grades the dangerous operations in a migration stream (drops, truncates, type
narrowing high; renames and NOT NULL without default medium) and generates the
rollback script in reverse execution order. Irreversible steps stay visible as
comments, and `-u` saves the rollback even when the gate fails — the changes
most worth blocking need the rollback most. Boundary vs schema_drift: drift
compares two snapshots, the guard audits one migration stream.

## Measure: histories and the overview

Every CLI/REST run of the five logging agents lands one JSONL record under
`logs/`; `hygiene-stats` / `metaquality-stats` print trends, every agent serves
`GET /api/<name>/stats`, and `/governance` aggregates the five histories into
one page: latest severity badges, trend lines, run counts.

## Gate: one pipeline, six checks

```yaml
- name: Warehouse governance gates
  run: |
    seatunnel-agent hygiene     --dir sql/ --exempt ci/exempt.yaml --fail-on orphans
    seatunnel-agent metaquality --dir sql/ --fail-on high
    seatunnel-agent contract    --dir sql/ -c ci/contract.yaml --fail-on high
    seatunnel-agent pii         --dir sql/ --mask --fail-on high
    seatunnel-agent grants      --dir sql/ --fail-on high
    seatunnel-agent ddlguard    --dir sql/ --fail-on high -u undo.sql
```

All deterministic, second-fast, zero tokens.

## Limits

Every verdict comes from static SQL and lineage: external readers, scheduler
context and real data distributions are invisible. Reports are leads, not
verdicts — the exemption lists and human review are part of the design.
