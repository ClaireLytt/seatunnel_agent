"""Platform plugin manifest — see seatunnel_agent.hub.registry."""

from seatunnel_agent.hub.registry import AgentManifest, ToolManifest

MANIFEST = AgentManifest(
    name="csv_doctor",
    workspace="data",
    route="/csvdoctor",
    page_title="CSV Doctor",
    logo="CD",
    color="#7f1d1d",
    title_en="CSV Doctor",
    title_zh="CSV 急救",
    desc_en="The file that will not parse or reads as mojibake — "
            "byte-level forensics, structural repair, and a fixed CSV "
            "out the other side",
    desc_zh="喂不进去或一打开是乱码的文件 — 字节取证 + 结构修复,另一头"
            "吐出能用的 CSV",
    api="seatunnel_agent.agents.data.csv_doctor.api:router",
    group="quality",
    order=107,
    external=True,
    tools=(
        ToolManifest(
            name="csv_doctor",
            ref="seatunnel_agent.agents.data.csv_doctor.tools:csv_doctor",
            desc_zh="CSV 急救（坏文件 → 诊断 + 修复版 CSV）",
            desc_en="CSV doctor (broken file → diagnosis + fixed CSV)",
            router_en="Triage and repair a broken CSV before any other "
                      "tool eats it: delimiter sniffing, BOM and "
                      "control-character stripping, double-encoded "
                      "mojibake recovery (UTF-8 read as cp1252, the "
                      "classic garbled Chinese) with before/after "
                      "samples, ragged-row padding and overflow "
                      "merging, duplicate-header suffixing, unbalanced "
                      "quotes and unrecoverable U+FFFD losses named. "
                      "The repaired CSV round-trips through this "
                      "workspace's parser. No database connection.",
            keywords=("csv", "乱码", "mojibake", "编码", "修复", "急救",
                      "bom", "分隔符", "脏数据", "garbled"),
        ),
    ),
)
