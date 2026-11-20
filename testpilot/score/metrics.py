"""Automatic scoring of one unit's final test file. No LLM judge."""

from pathlib import Path

from testpilot.mutation.runner import score_tests
from testpilot.sandbox.coverage_run import measure
from testpilot.sandbox.pytest_run import run_tests

FLAKY_RERUNS = 3


def is_flaky(repo_dir: Path, src: str, test_code: str) -> bool:
    """True if repeated runs of the same tests give different pass/fail sets."""
    runs = [run_tests(repo_dir, src, test_code) for _ in range(FLAKY_RERUNS)]
    seen = {(tuple(sorted(r.passed)), tuple(sorted(r.failed))) for r in runs}
    return len(seen) > 1


def score_unit(
    repo_dir: Path,
    src: str,
    unit: dict,
    test_code: str,
    seed: int = 0,
    reference_dir: Path | None = None,
    check_flaky: bool = False,
) -> dict:
    """Metrics for one unit. Units with no passing tests score zero on everything."""
    row = {"unit_id": unit["id"], "has_tests": bool(test_code)}
    if not test_code:
        return row | {"line_cov": 0.0, "branch_cov": None, "mutation_score": 0.0, "n_mutants": 0}
    cov = measure(repo_dir, src, unit, test_code)
    mut = score_tests(repo_dir, src, unit, test_code, seed=seed, reference_dir=reference_dir)
    row |= {
        "line_cov": cov.line_pct,
        "branch_cov": cov.branch_pct,
        "missing_lines": cov.missing_lines,
        "mutation_ok": mut.ok,
        "mutation_score": mut.score,
        "n_mutants": mut.total,
        "n_equivalent": mut.total - mut.scored,
        "survivors": [
            {"line": r.lineno, "operator": r.operator, "detail": r.detail}
            for r in mut.results
            if not r.killed and not r.equivalent
        ],
    }
    if check_flaky:
        row["flaky"] = is_flaky(repo_dir, src, test_code)
    return row
