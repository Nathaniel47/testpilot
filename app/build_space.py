"""Write the three files of the Hugging Face Space: python -m app.build_space

The Space does not hold a copy of the code. It installs this public repository at one pinned
commit, so what runs there is exactly what is on GitHub. Push that commit before deploying.
"""

import shutil
from pathlib import Path

from testpilot import config
from testpilot.llm.meta import git_commit

OUT = config.ROOT / "work" / "space_testpilot"
REPO = "https://github.com/Nathaniel47/testpilot"

APP = """# Entry point of the Space. The demo itself lives in the pinned testpilot package.
from testpilot.demo.page import build

build().launch()
"""


def requirements(commit: str) -> str:
    return f"testpilot @ {REPO}/archive/{commit}.zip\npytest>=8.0\ncoverage>=7.5\npsutil>=5.9\n"


def build_space(out: Path = OUT, commit: str | None = None) -> list[str]:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    shutil.copy(config.ROOT / "app" / "space" / "README.md", out / "README.md")
    (out / "app.py").write_text(APP, encoding="utf-8")
    (out / "requirements.txt").write_text(requirements(commit or git_commit()), encoding="utf-8")
    return sorted(p.name for p in out.iterdir())


if __name__ == "__main__":
    print(f"wrote {build_space()} to {OUT}")
