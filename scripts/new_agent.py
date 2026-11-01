"""Scaffold a new agent's mechanical surface in one command.

The agent factory's backend (core/i18n/api/tools/manifest) varies per
agent and stays hand-written — see docs/agent_factory.md.  What never
varies is the dance this script automates: the frontend workspace
(copied from a donor agent with the route rewritten), the npm workspace
registration, and the standard page-test spec.  ~10 shell calls become
one:

    python scripts/new_agent.py csv_doctor --route /csvdoctor \
        --page-title "CSV Doctor" [--from topic_schema]

Nothing here imports the (not yet written) backend, so the repo stays
green after scaffolding; the printed checklist covers the rest.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_CONFIGS = ("eslint.config.js", "postcss.config.js", "tailwind.config.ts",
            "tsconfig.app.json", "tsconfig.json", "tsconfig.node.json")
_SRC_COPY = ("index.css", "main.tsx", "vite-env.d.ts",
             "api.ts", "i18n.ts", "App.tsx")


def scaffold_frontend(repo: Path, name: str, route: str, page_title: str,
                      donor: str) -> list[str]:
    """Copy the donor workspace under the new name; returns created paths."""
    src = repo / "frontend" / donor
    dst = repo / "frontend" / name
    if not (src / "package.json").is_file():
        raise SystemExit(f"donor workspace frontend/{donor} not found")
    if dst.exists():
        raise SystemExit(f"frontend/{name} already exists")
    donor_route = re.search(
        r"base:\s*'(/[^']+)/'",
        (src / "vite.config.ts").read_text(encoding="utf-8")).group(1)
    donor_title = re.search(
        r"<title>([^<]+)</title>",
        (src / "index.html").read_text(encoding="utf-8")).group(1)

    (dst / "src").mkdir(parents=True)
    created = []

    def _port(rel: str, text: str) -> None:
        text = (text.replace(donor_route + "/", route + "/")
                    .replace("/api" + donor_route, "/api" + route)
                    .replace(f'"{donor}"', f'"{name}"')
                    .replace(donor_title, page_title))
        out = dst / rel
        out.write_text(text, encoding="utf-8", newline="\n")
        created.append(str(out.relative_to(repo)))

    for cfg in _CONFIGS:
        (dst / cfg).write_text((src / cfg).read_text(encoding="utf-8"),
                               encoding="utf-8", newline="\n")
        created.append(str((dst / cfg).relative_to(repo)))
    _port("index.html", (src / "index.html").read_text(encoding="utf-8"))
    _port("package.json", (src / "package.json").read_text(encoding="utf-8"))
    _port("vite.config.ts",
          (src / "vite.config.ts").read_text(encoding="utf-8"))
    for rel in _SRC_COPY:
        _port(f"src/{rel}",
              (src / "src" / rel).read_text(encoding="utf-8"))
    return created


def register_workspace(repo: Path, name: str, donor: str) -> None:
    """Insert the workspace right after the donor's entry."""
    pkg = repo / "frontend" / "package.json"
    text = pkg.read_text(encoding="utf-8")
    if f'"{name}"' in text:
        raise SystemExit(f"workspace {name} already registered")
    anchor = f'    "{donor}",\n'
    if anchor not in text:
        raise SystemExit(f"donor workspace entry '{donor}' not found in "
                         "frontend/package.json")
    pkg.write_text(text.replace(anchor, anchor + f'    "{name}",\n', 1),
                   encoding="utf-8", newline="\n")


def write_page_test(repo: Path, name: str, route: str,
                    page_title: str) -> str:
    slug = route.strip("/")
    out = repo / "tests" / f"test_{slug}_page.py"
    if out.exists():
        raise SystemExit(f"{out.name} already exists")
    body = f'''"""Browser tests for the React {route} page.

Standard two-test spec via tests.conftest.standard_page_tests —
the Playwright boilerplate lives in one deep module there.
Deselected by default:

    pytest -m uitest tests/test_{slug}_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import standard_page_tests

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.{name}.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "{slug}_demo"

globals().update(standard_page_tests(
    MANIFEST, "seatunnel_agent.agents.data.{name}.api:router",
    "{route}",
    env_var="{slug.upper()}_API_ALLOWED_DIRS", demo_dir=DEMO,
    heading="{page_title}", run_button="<TODO run button>",
    expect_texts=["<TODO expected text 1>", "<TODO expected text 2>"],
    llm_label="<TODO LLM checkbox label>"))
'''
    out.write_text(body, encoding="utf-8", newline="\n")
    return str(out.relative_to(repo))


_CHECKLIST = """
next steps (see docs/agent_factory.md):
  1. backend package src/seatunnel_agent/agents/data/{name}/
     (core + i18n + report + advisor_llm + api + tools + manifest +
      __init__; generators get a round-trip guard)
  2. CLI command in cli_cmds/quality_ops.py + register()
  3. demo under examples/{slug}_demo/ + backend tests
  4. fill the <TODO> markers in tests/test_{slug}_page.py
  5. edit frontend/{name}/src/(App|api|i18n).(tsx|ts)
  6. cd frontend && npm install && npx prettier --write {name}/src
     && (cd {name} && npm run lint && npm run build)
  7. neighbouring tool domains: add a PIN in
     tests/test_collision_guards.py
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("name", help="snake_case package/workspace name")
    ap.add_argument("--route", required=True, help="page route, e.g. /x")
    ap.add_argument("--page-title", required=True)
    ap.add_argument("--from", dest="donor", default="topic_schema",
                    help="donor workspace to copy (default topic_schema)")
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name):
        raise SystemExit("name must be snake_case")
    if not re.fullmatch(r"/[a-z0-9]+", args.route):
        raise SystemExit("route must look like /lowercase")

    repo = Path(__file__).resolve().parents[1]
    created = scaffold_frontend(repo, args.name, args.route,
                                args.page_title, args.donor)
    register_workspace(repo, args.name, args.donor)
    created.append(write_page_test(repo, args.name, args.route,
                                   args.page_title))
    print("created:")
    for c in created:
        print("  " + c)
    print(_CHECKLIST.format(name=args.name, slug=args.route.strip("/")))


if __name__ == "__main__":
    main()
