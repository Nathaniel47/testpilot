import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from testpilot.check import changed_python_files, check, eligible_units, summary_markdown
from testpilot.cli import build_parser, main

LIB = '''
def clamp(x: int, lo: int, hi: int) -> int:
    """Limit x to [lo, hi].

    >>> clamp(5, 0, 3)
    3
    >>> clamp(-1, 0, 3)
    0
    >>> clamp(2, 0, 3)
    2
    """
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def other(a: int) -> int:
    b = a + 1
    c = b * 2
    return c - 1
'''


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "sample"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "lib.py").write_text(LIB)
    return root


def test_only_changed_files_are_considered(repo):
    assert {u["qualname"] for u in eligible_units(repo, "pkg", ["pkg/lib.py"])} == {
        "clamp",
        "other",
    }
    assert eligible_units(repo, "pkg", ["pkg/other.py"]) == []


def test_check_scores_changed_functions_offline(repo):
    rows = check(repo, "pkg", ["pkg/lib.py"], mode="b0", max_units=1)
    assert len(rows) == 1 and rows[0]["has_tests"]
    assert 0 <= rows[0]["mutation_score"] <= 1
    text = summary_markdown(rows, "b0")
    assert "pkg/lib.py::" in text and "Mean mutation score" in text


def test_empty_summary_is_polite():
    assert "No eligible" in summary_markdown([], "b0")


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_changed_files_come_from_git_diff(repo):
    def git(*a):
        subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "feature")
    (repo / "pkg" / "lib.py").write_text(LIB + "\n# edit\n")
    (repo / "README.md").write_text("x")
    git("add", ".")
    git("commit", "-qm", "change")
    assert changed_python_files(repo, "main") == ["pkg/lib.py"]


def test_cli_check_writes_the_summary_file(repo, tmp_path):
    out = tmp_path / "summary.md"
    code = main(
        ["check", "--repo-dir", str(repo), "--src", "pkg", "--files", "pkg/lib.py",
         "--max-units", "1", "--summary", str(out)]
    )  # fmt: skip
    assert code == 0 and "TestPilot" in out.read_text(encoding="utf-8")


def test_all_planned_commands_exist():
    choices = build_parser()._subparsers._group_actions[0].choices
    assert {"ingest", "generate", "repair", "mutate", "report", "compare", "check"} <= set(choices)


def test_action_file_is_valid_and_has_no_secret_default():
    action = yaml.safe_load(Path("action/action.yml").read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    assert action["inputs"]["groq-api-key"]["default"] == ""
    assert action["inputs"]["mode"]["default"] == "b0"
