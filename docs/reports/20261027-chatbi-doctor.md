# 批次结果报告:chatbi 资产漂移体检 t2s-doctor(2026-10-27)

## 批准依据

> 用户对第八轮候选清单(建议"1(doctor)这一批")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `asset_findings`:示例库/收藏/看板/订阅 的静态漂移校验——SQL 过 validator+白名单(坏表 error、可疑列 warning,收藏的 `${宏}` 先替换占位字面量);订阅引用的指标/收藏存在性(缺失 error);每条带建议动作,error 排前 | health.py | 本批 |
| 高 | CLI `t2s-doctor --ddl ...`:四类资产一键体检,有 error 退出码 1(可做 CI 门禁/schema 变更后例行检查);单个存储读取失败不影响其余 | cli_cmds/text2sql.py | 本批 |
| — | 指南"资产漂移体检"节 | docs/chat_bi_guide.md | 本批 |

新增测试 1 条(9 断言):坏表 error / 坏列 warning / 看板坏项 / 订阅缺指标与缺收藏 / 宏收藏替换后通过 / 好资产零发现 / error 在前。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_subscriptions.py::test_asset_doctor_findings -q -> 1 passed
python -m pytest -q          -> 3451 passed, 1 skipped, 243 deselected in 157.24s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3450 → 3451 passed(+1,含 9 断言)。
- 行为:schema/指标库变更后,四类无人值守资产的失配从"凌晨运行时炸"提前到"一条命令可见";其余路径不变。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | doctor 未接 CI(需要仓库里有真实资产文件与 DDL 才有意义) | t2s-doctor | 资产是部署态数据,CI 里通常为空 | 仅限手动/定时执行 | 部署侧 cron 每日跑一次即可 |
| 低 | mypy 白名单不含 text2sql(上批遗留,未动) | pyproject.toml | 建议单独批次 | 同上批 | 单独批次扩白名单 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
