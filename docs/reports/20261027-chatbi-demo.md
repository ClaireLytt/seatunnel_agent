# 批次结果报告:一键演示环境 chatbi-demo(2026-10-27)

## 批准依据

> 用户对第十五轮候选(建议"1(demo)")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | `demo.py build_demo`:确定性(seed=42)生成 60 天 sqlite 销售数据——星期形态(周末 0.7×)、节假日抬升(1.4×,走 calendar_cn)、D-10 人造退款尖峰(18% vs 常态 5%),三渠道四省份 | demo.py(新) | 本批 |
| 中高 | 全特性 metrics.yaml(ratio/tree/targets/aliases 全带)+ 匹配 DDL + QUESTIONS.md(10 个演示问题覆盖 查询/口径/因子树/节假日时间/预测/目标/相关/异动/相对期/溯源 + 订阅演示命令) | demo.py | 本批 |
| — | CLI `chatbi-demo --dir --days`:生成后自检(DDL×metrics 交叉校验失败即报错),输出启动指引(SCHEMA_DDL_PATH/T2S_METRICS_PATH) | cli_cmds/text2sql.py | 本批 |
| — | 指南"快速开始"加零配置入口 | docs/chat_bi_guide.md | 本批 |

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 173 source files
python -m pytest -q -k demo  -> 1 passed（自洽性:指标零错误/35 天/>500 行/尖峰日退款率 >2× 常态）
真实 CLI 调用               -> rc=0,输出 1348 行/35 天/尖峰日与启动指引
python -m pytest -q          -> 3463 passed, 1 skipped, 243 deselected in 160.07s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3462 → 3463 passed(+1)。
- 行为:新增 `chatbi-demo` 命令;演示资产写入独立目录(默认 demo/chatbi),不触碰用户 config/。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 演示订阅以"可复制命令"形式给出而非自动创建 | QUESTIONS.md | 避免写入用户真实订阅文件 | 多两步手动操作 | 符合预期,保持 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动;CLI 已真实调用验证)。
- 其余无。
