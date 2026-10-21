# 01: 两张紫卡换色 + hub 截图

**What to build:** orchestrator(#7c3aed)与 issue_triage(#9333ea)manifest color 换为合规(非蓝紫)且与其余 23 卡去重的色值;列 25 卡现值表作证据;起 hub 截 /ai 首页供用户过目;AIP1 冒烟回归不破。

**Blocked by:** None

**Status:** ready-for-agent

- [ ] 两色合规、不与现有任何卡撞色(附表)
- [ ] hub /ai 截图产出(路径汇报)
- [ ] ruff + pytest tests/test_registry.py tests/test_hub_pages.py 绿
