"""Build the static demo.

    python -m app.build_static results   # run the pipeline on the examples, save the results
    python -m app.build_static space     # write the Space files, pinned to the current commit

The Space cannot run code, so it shows results saved by the real pipeline. Its index.html only
loads app/static/page.js and results.json from this public repository at one pinned commit.
Commit and push before building the Space files.
"""

import json
import shutil
import sys
from pathlib import Path

from testpilot import config
from testpilot.demo.core import EXAMPLES, analyze
from testpilot.llm.meta import git_commit

STATIC = config.ROOT / "app" / "static"
RESULTS = STATIC / "results.json"
OUT = config.ROOT / "work" / "space_testpilot"
CDN = "https://cdn.jsdelivr.net/gh/Nathaniel47/testpilot"
KEEP = (
    "line_cov",
    "branch_cov",
    "mutation_score",
    "n_mutants",
    "survivors",
    "test_code",
    "seconds",
)

SPACE_README = """---
title: TestPilot
emoji: 🧪
colorFrom: blue
colorTo: gray
sdk: static
pinned: false
---

TestPilot demo: saved results of generated tests, scored by coverage and mutation score.
Source and study: https://github.com/Nathaniel47/testpilot
"""


def make_results(path: Path = RESULTS) -> list[dict]:
    rows = []
    for name, code in EXAMPLES.items():
        row = analyze(code)
        rows.append({"name": name, "code": code} | {k: row.get(k) for k in KEEP})
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"generator": "offline template (B0)", "examples": rows}
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    return rows


def index_html(commit: str) -> str:
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>TestPilot demo</title>\n"
        '<div id="app">Loading the TestPilot demo...</div>\n'
        f'<script src="{CDN}@{commit}/app/static/page.js"></script>\n'
    )


def build_space(out: Path = OUT, commit: str | None = None) -> list[str]:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    (out / "README.md").write_text(SPACE_README, encoding="utf-8", newline="\n")
    (out / "index.html").write_text(
        index_html(commit or git_commit()), encoding="utf-8", newline="\n"
    )
    return sorted(p.name for p in out.iterdir())


if __name__ == "__main__":
    if sys.argv[1:] == ["results"]:
        print(f"saved {len(make_results())} example results to {RESULTS}")
    elif sys.argv[1:] == ["space"]:
        print(f"wrote {build_space()} to {OUT}")
    else:
        raise SystemExit(__doc__)
