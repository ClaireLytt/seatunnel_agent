-- DAG 体检演示 · 依赖成环：tmp.a ↔ tmp.b（调度器无法编排）
INSERT OVERWRITE TABLE tmp.a
SELECT k, v FROM tmp.b;

INSERT OVERWRITE TABLE tmp.b
SELECT k, v FROM tmp.a;
