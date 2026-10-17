# 05: Global options + connection presets

**What to build:** The options block (WHERE, numeric threshold, key columns, column mapping, sampling strategy with conditional stratified column, masking) feeds every action, with a one-click reset. Connection presets (name + environment) can be saved per side, loaded (auto-apply on select), and deleted, backed by the existing presets store.

**Blocked by:** 02 — Walking skeleton

**Status:** ready-for-agent

- [ ] Options affect comparison semantics as legacy (verified via API test with threshold/WHERE)
- [ ] Reset restores all option defaults
- [ ] Presets save/load/delete round-trip; load fills the connection form
- [ ] Project verification commands green
