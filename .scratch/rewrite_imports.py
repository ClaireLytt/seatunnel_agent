import pathlib
import re

shared = {"_build_webhook_summary", "_details_card", "_error_html", "_esc_html",
          "_send_webhook", "_validate_where", "_with_validation",
          "_get_matplotlib", "_log"}
reports = {"_export_report_csv", "_export_report_excel", "_download_dir"}


def mod_for(sym):
    if sym in shared:
        return "ui_shared"
    if sym in reports:
        return "ui_reports"
    return "ui_cards"


for f in ["tests/test_data_comparison.py", "tests/test_chunked_compare.py"]:
    p = pathlib.Path(f)
    src = p.read_text(encoding="utf-8")

    def repl_single(m):
        return ("from seatunnel_agent.agents.data.data_comparison."
                f"{mod_for(m.group(1))} import {m.group(1)}")

    src = re.sub(
        r"from seatunnel_agent\.agents\.data\.data_comparison\.ui import (\w+)$",
        repl_single, src, flags=re.M)

    def repl_multi(m):
        indent = m.group(1)
        names = [n.strip().rstrip(",") for n in m.group(2).split("\n")
                 if n.strip().rstrip(",")]
        groups = {}
        for n in names:
            groups.setdefault(mod_for(n), []).append(n)
        out = []
        for mod in sorted(groups):
            body = "\n".join(f"{indent}    {n}," for n in groups[mod])
            out.append(f"{indent}from seatunnel_agent.agents.data."
                       f"data_comparison.{mod} import (\n{body}\n{indent})")
        return "\n".join(out)

    src = re.sub(
        r"( *)from seatunnel_agent\.agents\.data\.data_comparison\.ui import \(\n"
        r"((?:\s+\w+,?\n)+)\1\)",
        repl_multi, src)
    p.write_text(src, encoding="utf-8")
print("rewritten")
