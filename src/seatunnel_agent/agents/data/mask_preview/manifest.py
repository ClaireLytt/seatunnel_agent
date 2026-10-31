"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="mask_preview",
    workspace="data",
    route="/maskpreview",
    page_title="Mask Preview",
    logo="MP",
    color="#9f1239",
    title_en="Mask Preview",
    title_zh="脱敏预览",
    desc_en="Real data rows — sensitive columns detected by name and "
            "value shape, masked format-preserving, previewed before "
            "and after",
    desc_zh="真实数据行 — 列名+值形态双判定敏感列,保格式脱敏,前后对照"
            "预览,外发测试/演示前最后一道检查",
    api="seatunnel_agent.agents.data.mask_preview.api:router",
    group="governance",
    order=94,
    external=True,
    tools=(
        ToolManifest(
            name="mask_preview",
            ref="seatunnel_agent.agents.data.mask_preview.tools:mask_preview",
            desc_zh="脱敏预览（数据行 → 规则表 + 脱敏样例）",
            desc_en="Mask preview (rows → rules + masked sample)",
            router_en="Mask a pasted CSV/JSONL sample before it leaves "
                      "for a test or demo environment: sensitive "
                      "columns are detected by column name (the "
                      "pii_scan catalog) and by value shape (CN phone, "
                      "ID card, email, bank card), then masked "
                      "format-preserving (138****1234, a***@host, "
                      "**** **** **** 1234) with a before/after "
                      "preview. Distinct from pii_scan, which plans "
                      "SQL-level masking from DDL and lineage. Nothing "
                      "leaves the process.",
            keywords=("脱敏", "mask", "敏感", "pii", "预览", "手机号",
                      "身份证", "邮箱", "样例", "外发"),
        ),
    ),
)
