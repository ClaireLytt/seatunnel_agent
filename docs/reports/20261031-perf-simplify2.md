# 批次结果报告:性能套件四~七期 simplify 回扫(2026-10-31)

## 批准依据

> "go on"(功能批次后按惯例做四视角质量回扫,/simplify,
> 范围 1080353^..HEAD)

## 已修复(四视角去重后)

| 视角 | 内容 |
| --- | --- |
| 层次+复用+化简 | placement 排序规则此前在 conflictor.place / render_place / CLI 闸门三处手抄 — 收敛为 place() 内的 rank() 并返回 declared_is_best,渲染与闸门只读该字段 |
| 层次+复用 | --promote-baseline 手搓的 jsonl 追加(ts 格式/append)与 track_history 重复 — 抽出 check_runner.append_jsonl,两处共用(顺带补上 mkdir parents) |
| 层次+化简 | sqlcost --dir 批量逻辑整块住在 CLI 层且表头仅英文 — 下沉为 estimator.estimate_batch + report.render_batch(zh/en i18n、fmt_bytes),CLI 只剩读目录+闸门,API 层随时可接 |
| 化简+层次 | 新增 common.utils.md_table,本批 7 处手搓 markdown 表(place/audit/roi/compare/sqlperf diff/slowquery diff x2/salt what-if/batch)全部收敛,消掉约百行 "\| ... \|" 脚手架 |
| 效率 | index_advisor/roi.py 基线估算提到表循环外 — 原来 2*T*S 次完整解析+估算,现在 S+T*S 次,表多时近乎减半 |
| 复用 | index_advisor 两个 CREATE TABLE 分段正则共享同一 head 模式串,消除边界 case 漂移 |
| 化简 | slowquery --trend 改用 click.IntRange(min=2),删掉 ValueError 二次包装;skew fat_tails 改为前置初始化删掉 else 分支 |
| 复用 | sqlperf --before 与 slowquery --diff 的文件读取改走 check_runner.read_input,错误口径统一 |

## 跳过(记录原因)

- skew-runtime --fail 改走 fail_check:该文件既有门禁就是 print+exit
  风格,单独改一处反而不一致;留给整文件迁移时一起做。
- API/CLI "计算→payload→render"胶水组合器:两位审查者均判当前
  属过度设计,出现第 5 个入口面再抽。
- dagconflict place() 对 others 间写冲突逐候选重算:粘贴场景毫秒级,
  判为可接受。
- safe_ratio 公共化:三处闭包语义不同(倍率 vs 省比),合并不净赚。
- --what-if-salt 的 ValueError 包装保留:0=自动、>=2 显式的取值域
  IntRange 表达不了。

## 验证结果

```
pytest tests (非 uitest) -> 3845 passed, 1 skipped
ruff src/seatunnel_agent -> All checks passed
mypy(触及的 43 个文件) -> no issues
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```
