// Cross-page SQL hand-off over localStorage (the "bridge").
// Python-side twin: src/seatunnel_agent/common/bridge.py — tests/test_bridge.py
// keeps the two in sync.
export const TRANSPILE_SQL_KEY = 'st_transpile_sql'
export const DATASKEW_SQL_KEY = 'st_dataskew_sql'
