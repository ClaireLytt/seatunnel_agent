# 批次结果报告:scanpage-seam(2026-10-29)

## 批准依据

> 用户批示:"go on"(持续改进循环)。四个扫描页(metaquality/contract/grants/ddlguard)的 App.tsx 已是四份近似拷贝——4 个 adapter 使 seam 成为真实 seam,按 codebase-design 原则收敛。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | shared 新增 ScanPage 组件:目录/方言/主按钮 + 折叠粘贴区 + 报告面板 + 结构化错误处理;可选 extra 文本域(必填校验,如契约 YAML)、detailsOpen、行数配置;i18n 键约定留在各 app | frontend/shared/src/components/ScanPage.tsx | 本批次 |
| 高 | 四个页面收敛为 15-17 行配置(原各 ~140 行);contract 的 i18n 键改为 extra_* 约定 | 四个 App.tsx, contract_check/src/i18n.ts | 本批次 |

## 验证结果

```
npm run build --workspace {metadata_quality,contract_check,grant_scan,ddl_guard}
  -> 全部 built(2.8-3.4s)
npm run lint(四个 app)-> clean
python -m pytest -m uitest tests/test_metaquality_page.py tests/test_contract_page.py tests/test_grants_page.py tests/test_ddlguard_page.py -q
  -> 10 passed in 31.42s(行为逐一保留:契约必填提示、报告类名、折叠默认态)
```

```
check_workflow 输出(提交后运行):
[PASS] AI 署名: 无 AI 署名(范围 origin/pso..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/pso..HEAD)
```

## 前后差异

- 4 × ~140 行拷贝 → 1 个深组件 + 4 份 15-17 行配置;下一个扫描 agent 的页面成本= 一份 i18n + 一份 api.ts + 一个配置。
- 10 条既有 Playwright 页测零改动通过——界面行为与收敛前逐一一致。
- 类型教训:让 cfg.scan 收 `ScanBody`(具名字段 ∩ 索引签名)而不是让各 app 强转;contract 的必填 contract 字段在配置处包一层显式收窄。
- pii_scan 与 lineage_hygiene 页各有专属交互(mask 按钮/豁免输入),暂不并入;第三类形状出现时再扩展 ScanPage。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

无。
