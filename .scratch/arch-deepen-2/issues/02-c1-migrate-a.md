# 02: C1 migrate A — 8 个页测文件切换

**What to build:** orchestrator/llmeval/promptlab/llmcost/codefix/webtask 及 2 个早期迁移页测切到 conftest 工厂(含特例:codefix/webtask 的门 env 留空、llmcost 的 demo 数据 env、llmeval 的 LLM_EVAL_PATH、promptlab 的 PROMPT_LAB_PATH、orchestrator 的 neutralize 组合),删除本地夹具副本。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 8 个文件 `-m uitest` 全绿;每文件 −40~50 行
- [ ] ruff 通过
