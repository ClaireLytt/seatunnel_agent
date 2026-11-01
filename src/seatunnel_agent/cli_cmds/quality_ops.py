"""质量/治理/建设/运维 CLI 命令的聚合注册器.

命令本体按 manifest group 分住 qo_quality / qo_governance / qo_build /
qo_ops 四个模块（2026-10-31 拆分,2530 行 → 4 个子模块）;本文件只负责
一次性注册,保持 cli_cmds.__init__ 的接缝不变。
"""

from __future__ import annotations

from . import qo_build, qo_governance, qo_quality


def register(cli) -> None:
    qo_quality.register(cli)
    qo_governance.register(cli)
    qo_build.register(cli)
