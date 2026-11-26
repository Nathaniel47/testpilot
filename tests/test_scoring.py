import pytest

from testpilot.context.builder import RepoIndex, build_context
from testpilot.generate import guided
from testpilot.llm.budget import Budget
from testpilot.llm.cache import Cache
from testpilot.llm.client import LLMClient
from testpilot.llm.providers import Completion
from testpilot.report.tables import comparison_markdown, mode_summary, paired_difference
from testpilot.sandbox.coverage_run import measure
from testpilot.score.metrics import score_unit
from testpilot.score.stats import bootstrap_ci

LIB = """
def sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
"""
HEAD = "from pkg.lib import sign\n\n\n"
ONE = HEAD + "def test_pos():\n    assert sign(5) == 1\n"
THREE = (
    ONE + "\n\ndef test_neg():\n    assert sign(-5) == -1\n\n\n"
    "def test_zero():\n    assert sign(0) == 0\n"
    "    assert sign(1) == 1\n    assert sign(-1) == -1\n"
)


def fenced(code):
    return "```python\n" + code + "```"


@pytest.fixture
def repo(tmp_path):
    pkg = tmp_path / "repo" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "lib.py").write_text(LIB)
    return tmp_path / "repo"


def unit_for(repo):
    index = RepoIndex(repo, "pkg")
    unit = {
        "id": "sign", "file": "pkg/lib.py", "qualname": "sign", "kind": "function",
        "lineno": 2, "end_lineno": 7, "sha256": "s1",
    }  # fmt: skip
    return unit, build_context(unit, index)


def fake_client(tmp_path, replies):
    calls = []

    def fake(model, system, prompt, temperature, seed, max_tokens):
        calls.append(prompt)
        return Completion(replies[min(len(calls) - 1, len(replies) - 1)], 10, 10)

    client = LLMClient(
        provider="groq",
        cache=Cache(tmp_path / "cache"),
        budget=Budget(tmp_path / "b.json", 1_000_000),
        call_fn=fake,
        max_tokens=10,
    )
    return client, calls


def test_coverage_reports_missing_lines_of_the_unit_only(repo):
    unit, _ = unit_for(repo)
    cov = measure(repo, "pkg", unit, ONE)
    assert cov.ok and cov.line_pct < 1 and cov.missing_lines == [5, 6, 7]
    full = measure(repo, "pkg", unit, THREE)
    assert full.line_pct == 1 and full.branch_pct == 1


def test_score_unit_without_tests_is_zero_not_missing(repo):
    unit, _ = unit_for(repo)
    row = score_unit(repo, "pkg", unit, "")
    assert row["mutation_score"] == 0.0 and row["line_cov"] == 0.0 and not row["has_tests"]


def test_score_unit_combines_coverage_and_mutation(repo):
    unit, _ = unit_for(repo)
    weak, strong = score_unit(repo, "pkg", unit, ONE), score_unit(repo, "pkg", unit, THREE)
    assert strong["line_cov"] > weak["line_cov"]
    assert strong["mutation_score"] > weak["mutation_score"]
    assert weak["survivors"]


def test_m3_feeds_survivors_back_and_keeps_the_better_tests(repo, tmp_path):
    unit, ctx = unit_for(repo)
    client, calls = fake_client(tmp_path, [fenced(ONE), fenced(THREE)])
    out = guided.run_m3(client, ctx, repo, "pkg", unit)
    assert "not caught" in calls[1] or "NOT caught" in calls[1]
    assert "test_zero" in out.test_code and out.calls >= 2


def test_m2_asks_about_missing_lines(repo, tmp_path):
    unit, ctx = unit_for(repo)
    client, calls = fake_client(tmp_path, [fenced(ONE), fenced(THREE)])
    out = guided.run_m2(client, ctx, repo, "pkg", unit)
    assert "never executed" in calls[1] and "6:" in calls[1]
    assert "test_neg" in out.test_code


def test_a_worse_candidate_is_not_kept(repo, tmp_path):
    unit, ctx = unit_for(repo)
    client, _ = fake_client(tmp_path, [fenced(THREE), fenced(ONE)])
    out = guided.run_m3(client, ctx, repo, "pkg", unit)
    assert "test_zero" in out.test_code


def test_bootstrap_interval_is_seeded_and_brackets_the_mean():
    values = [0.0, 0.5, 1.0, 0.75, 0.25, 0.9]
    a, b = bootstrap_ci(values, seed=3), bootstrap_ci(values, seed=3)
    assert a == b and a[0] <= sum(values) / len(values) <= a[1]
    assert bootstrap_ci([1.0]) is None


def test_comparison_table_has_every_mode_and_a_paired_difference():
    def rows(scale):
        return {
            f"u{i}": {
                "unit_id": f"u{i}", "has_tests": True, "line_cov": 0.9,
                "branch_cov": 0.8, "mutation_score": scale * i / 5, "n_mutants": 10,
                "tokens": 100,
            }
            for i in range(1, 6)
        }  # fmt: skip

    scores = {"m2": rows(0.5), "m3": rows(0.9)}
    text = comparison_markdown(scores)
    assert "| M2 |" in text and "| M3 |" in text and "M3 minus M2" in text
    assert mode_summary(list(scores["m2"].values()))["gap"].startswith("+")
    assert paired_difference(scores["m2"], scores["m3"], "mutation_score").startswith("+0.")
