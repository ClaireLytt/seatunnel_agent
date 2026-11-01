# Agent 100 csv_doctor — CSV 急救（含原 97 编码取证,合并交付）

日期: 2026-10-31 分支: fresh

## 内容

- **脚手架首战**：`python scripts/new_agent.py csv_doctor --route /csvdoctor --page-title "CSV Doctor"` 一条命令产出 16 个前端文件 + workspace 注册 + 页面测试 spec（TODO 位）,替代以往 ~10 次手工调用。踩到一个环境坑:Git Bash 会把 `/csvdoctor` 做 MSYS 路径转换,需 `MSYS_NO_PATHCONV=1`（已记录）。
- `agents/data/csv_doctor/`：doctor（字节取证 + 结构修复）、i18n、report、advisor_llm（可选事故说明,只发诊断元数据）、api、tools、manifest（group quality, /csvdoctor）。
- 诊断七码：CD001 BOM 剥除（low）;CD002 列数漂移行,短行补空/溢出并入末列（≥20% high）;CD003 引号不配对（medium）;CD004 U+FFFD 字节已丢失不可修（high,点名重新导出）;CD005 双重编码乱码复原（cp1252/latin-1 回转,带前后对照样例,medium）;CD006 控制字符剥除（low）;CD007 表头重名加后缀（medium）。分隔符按列数一致性从 `, ; | \t` 嗅探。
- **回检守卫**：修复版 CSV 必须通过 sample_profile.parse_rows 且行列数一致才返回——产出可直接喂给本工作台所有吃行数据的 agent（输入侧闭环）。
- CLI `csvdoctor`（-f/--text/--csv-out 另存/--llm/--fail-on-high gate）;页面提供修复版 CSV 下载。
- 测试：`tests/test_csv_doctor.py` 13 项（七码齐打/乱码前后对照/分级边界/tab 嗅探/回检/另存）;页面 spec 2 项。页面演示乱码串以 `\u` 转义写入,避免源码里裸 C1 控制符（eslint no-irregular-whitespace 连模板展开值一起查,转义 BOM 也拦——演示去 BOM,文件 demo 保留覆盖 CD001）。
- 示例 `examples/csvdoctor_demo/broken.csv`（真实双重编码字节,由脚本生成避免 Write 规范化）。

## 验证

```
tests\test_csvdoctor_page.py ..                                          [100%]
============================== 2 passed in 8.64s ==============================

tests/test_csv_doctor.py + test_registry.py + test_hub_pages.py + test_collision_guards.py
======================= 50 passed, 2 warnings in 14.86s =======================
All checks passed!   (ruff)
```

前端 `npm run lint` 零告警，`npm run build` 成功。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
