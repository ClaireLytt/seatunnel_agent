# 批次结果报告:uiskill CI 字体 flake 加固(2026-10-28)

## 批准依据

> 用户:"批次 1"(批次内容:修 uiskill CI 的两个失败——字体测试防残缺系统字体、3 份报告补验证输出)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `test_export_pdf_cjk_font_registration` 捕获 `TTLibError` 并 skip:ubuntu runner 偶现裁剪过的 DejaVuSans(glyf 表截断,CI run 40413985210 报 `expected 557508 bytes but got 33464`),属环境字体损坏,非被测的 add_font 签名回归 | tests/test_text2sql.py | 本批次提交 |
| — | 报告补验证输出、字体原子写:经查已由先前提交 1820d55 完成并推送,最新 uiskill CI(run 40414783601/633/604)lint/tests/ui-smoke 全绿,本批次未重复改动 | docs/reports/20261026-chatbi-*.md | 1820d55 |

## 验证结果

```
ruff check src tests scripts                      -> All checks passed!
mypy                                              -> Success: no issues found in 175 source files
pytest tests/test_text2sql.py::TestExportExcelPdf -q -> 6 passed in 11.41s
python scripts/check_workflow.py                  -> 见下方贴附输出
```

check_workflow 输出:

```
[PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 已粘贴 check_workflow 输出
[PASS] floor: 无作弊变绿改动
```

## 前后差异

- 测试类:修改前,残缺系统字体机器上该用例 FAILED(`TTLibError: unexpected end of 'glyf' table data`,CI run 40413985210);修改后本机 `TestExportExcelPdf` 6 passed,残缺字体环境将 skip 而非 FAIL。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | ubuntu runner 自带 DejaVuSans 偶现截断的根因未定位(同日 22:38 失败、22:44 重跑即通过) | CI run 40413985210 vs 40414783633 | runner 镜像差异,无法本地复现 | 仅影响该回归测试的字体候选,已通过 skip 化解 | 观察;若复现频繁再为候选字体加 fontTools 预校验 |

## 未执行的步骤

- 全量 pytest / uitest smoke:未执行。本批次仅改一个测试用例的异常处理,按第 8 节跑了 ruff/mypy + 定向测试;全量结果以 CI 为准。
