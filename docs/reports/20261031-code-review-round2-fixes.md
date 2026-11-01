# 代码评审（第二轮,origin/fresh...HEAD,55 提交）修复

日期: 2026-10-31 分支: fresh

## 评审发现与处置

Standards 轴:
1. ddl_evolve `_change_column` mysql/hive 分支逐字节相同（死分支）→ 收敛为单
   return,注释说明两方言 CHANGE COLUMN 同拼写,`del dialect` 保留接缝参数。
2. mock_data 跨包引用 mask_preview 下划线私有 `_detect_by_name/_detect_by_value`
   → mask_preview 新增公共接缝 `detect_category(name, values)`（导出到
   __init__/__all__）,mock_data 改走公共口（与 dup_pipeline 用
   statement_shapes 的先例一致）。
3. 91×App.tsx / tools.py 包装层重复——架构复盘已记录"等第二个 adapter"暂缓,
   不重复处置。

Spec 轴:
1. sla_board 同一行 deadline/finish 混用 HH:MM 与 ISO 时静默产出荒谬迟到值
   （两种格式量纲不同:当日分钟 vs epoch 分钟）→ `_to_minutes` 返回
   (minutes, kind),行内两种 kind 不一致即 ValueError;补回归测试
   `test_mixed_time_formats_in_one_row_raise`。
2. field_usage 把 `COUNT(*)` 里的星号误判为 SELECT * 盲区（FU003 误报 +
   连带豁免 FU002）→ 只认投影位置的星号（父节点为 exp.Select 的裸 * 或
   exp.Column 的 t.*）,聚合内星号不计;补回归测试
   `test_count_star_is_not_a_blind_spot`。

全量回归新抓一处:
3. ddl_evolve 关键词 `迁移/脚本/上线` 抢走 ddl_guard 的既有路由
   （test_ddl_guard 路由断言失败）→ 收窄 ddl_evolve 关键词为
   快照/生成/加列/改列等独有问法,存量路由不动。

## 验证

```
受影响套件:
============================= 57 passed in 3.76s ==============================
路由修复后:
======================= 43 passed, 2 warnings in 13.82s =======================
全量:
=== 4525 passed, 1 skipped, 382 deselected, 3 warnings in 169.39s (0:02:49) ===
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
