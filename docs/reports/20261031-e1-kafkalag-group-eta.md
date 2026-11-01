# E1 kafka_lag 组级追平汇总（增强）

日期: 2026-10-31 分支: fresh

## 去重核对

原提案"追平 ETA / 永远追不平点名 / 建议并发"实现前核对发现大半已存在:
KL005 逐分区追平 ETA、KL003 追不上（net<=0）、KL004 停摆均为既有功能——
按去重纪律收窄为真缺口:**组级汇总**（值班第一眼要的是"全组多久追平",
不是逐分区清单）。"建议并发"需要消费者数输入,快照里没有,不做。

## 改动

- `LagResult` 新增 `group_eta_min`（全组追平分钟 = 有速率分区的 ETA 最大
  值,最慢分区决定;任一分区追不上或无速率则为 None）与 `never_count`
  （追不上的分区数）,入 to_dict。
- 报告摘要行追加:`· 全组约 N 分钟追平（最慢分区决定）` 或
  `· N 个分区按当前速率永远追不平`;无速率时保持原样。
- 测试 +3:最慢分区决定、任一 behind 即 never、无速率不出汇总。
  （修正了自己测试里把秒当分钟的期望值笔误。）

## 验证

```
tests/test_kafka_lag.py
============================= 26 passed in 3.61s ==============================
tests/test_kafkalag_page.py (uitest)
============================== 2 passed in 7.74s ==============================
All checks passed!   (ruff)
```

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
