"""Run a unit's tests against each mutant inside one sandbox.

A mutant is killed when the tests fail, error, or time out on it. Before scoring, the tests must
pass on the unparsed-but-unmutated file; otherwise the number would mean nothing.
"""

from dataclasses import dataclass, field
from pathlib import Path

from testpilot.mutation.mutate import Mutant, baseline_code, make_mutants, read_file
from testpilot.sandbox.pytest_run import TEST_FILE
from testpilot.sandbox.runner import Sandbox


@dataclass
class MutantResult:
    id: str
    operator: str
    lineno: int
    detail: str
    killed: bool
    equivalent: bool = False  # survived the repo's own tests too: probably the same behaviour


@dataclass
class MutationReport:
    ok: bool  # False when the tests failed on the unmutated code
    results: list[MutantResult] = field(default_factory=list)
    note: str = ""

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def killed(self) -> int:
        return sum(r.killed for r in self.results)

    @property
    def scored(self) -> int:
        return sum(not r.equivalent for r in self.results)

    @property
    def score(self) -> float | None:
        """killed / (mutants not flagged equivalent); None when there is nothing to score."""
        if not self.ok or not self.scored:
            return None
        return sum(r.killed for r in self.results if not r.equivalent) / self.scored


def sandbox_path(unit_file: str, src: str) -> str:
    return (Path(src).name / Path(unit_file).relative_to(src)).as_posix()


def score_tests(
    repo_dir: Path,
    src: str,
    unit: dict,
    test_code: str,
    seed: int = 0,
    limit: int = 40,
    reference_dir: Path | None = None,
) -> MutationReport:
    file_text = read_file(repo_dir, unit["file"])
    mutants = make_mutants(file_text, unit["qualname"], unit["sha256"], seed, limit)
    target = sandbox_path(unit["file"], src)
    with Sandbox() as sb:
        sb.copy_tree(repo_dir / src, Path(src).name)
        sb.write(TEST_FILE, test_code)
        sb.write(target, baseline_code(file_text))
        base = _run(sb, 60)
        if not base.ok:
            return MutationReport(ok=False, note="tests fail on unmutated code")
        timeout = max(5.0, base.seconds * 3 + 2)
        report = MutationReport(ok=True)
        for m in mutants:
            sb.write(target, m.code)
            res = _run(sb, timeout)
            report.results.append(MutantResult(m.id, m.operator, m.lineno, m.detail, not res.ok))
        sb.write(target, baseline_code(file_text))
    if reference_dir is not None:
        flag_equivalent(report, mutants, repo_dir, src, unit, reference_dir)
    return report


def _run(sb: Sandbox, timeout: float):
    return sb.run_pytest(TEST_FILE, "-x", "-q", "-p", "no:cacheprovider", timeout=timeout)


def flag_equivalent(report, mutants: list[Mutant], repo_dir, src, unit, reference_dir) -> None:
    """Mark survivors that also survive the repo's own tests. Heuristic, not a proof."""
    survivors = [m for m, r in zip(mutants, report.results, strict=True) if not r.killed]
    if not survivors:
        return
    by_id = {r.id: r for r in report.results}
    target = sandbox_path(unit["file"], src)
    with Sandbox() as sb:
        sb.copy_tree(repo_dir / src, Path(src).name)
        sb.copy_tree(reference_dir, "reference")
        sb.write(target, baseline_code(read_file(repo_dir, unit["file"])))
        base = sb.run_pytest("reference", "-x", "-q", "-p", "no:cacheprovider", timeout=300)
        if not base.ok:
            return  # the reference suite does not run cleanly here, so say nothing
        for m in survivors:
            sb.write(target, m.code)
            res = sb.run_pytest(
                "reference", "-x", "-q", "-p", "no:cacheprovider", timeout=max(30, base.seconds * 3)
            )
            by_id[m.id].equivalent = res.ok
