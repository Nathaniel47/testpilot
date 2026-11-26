"""M2 coverage-guided and M3 mutation-guided generation.

Both start from M1's passing tests, then ask the model for a better full test file using one
automatic signal: lines never executed (M2, the coverage-only comparison) or mutants that
survived (M3). A candidate is kept only if it passes on the original code AND the signal
improves, so a guided round can never make a unit worse.
"""

from dataclasses import replace
from pathlib import Path

from testpilot.context.builder import Context
from testpilot.generate import modes
from testpilot.generate.parse_response import extract_tests
from testpilot.generate.prompts import SYSTEM, coverage_prompt, mutant_prompt
from testpilot.mutation.mutate import read_file
from testpilot.mutation.runner import score_tests
from testpilot.repair.loop import Outcome, count_tests, repair
from testpilot.sandbox.coverage_run import measure

GUIDED_ROUNDS = 2


def _numbered(repo_dir: Path, unit: dict, wanted: list[int]) -> str:
    lines = read_file(repo_dir, unit["file"]).splitlines()
    return "\n".join(f"{n}: {lines[n - 1].strip()}" for n in wanted if 0 < n <= len(lines))


def _coverage_signal(repo_dir, src, unit, code):
    cov = measure(repo_dir, src, unit, code)
    if not cov.ok:
        return -1.0, ""
    # Reward line plus branch coverage together, so a branch-only gap still counts.
    parts = [p for p in (cov.line_pct, cov.branch_pct) if p is not None]
    text = _numbered(repo_dir, unit, cov.missing_lines)
    return (sum(parts) / len(parts) if parts else 1.0), text


def _mutation_signal(repo_dir, src, unit, code):
    report = score_tests(repo_dir, src, unit, code)
    if not report.ok or report.score is None:
        return -1.0, ""
    lines = [
        f"line {r.lineno}: {r.detail}" for r in report.results if not r.killed and not r.equivalent
    ]
    return report.score, "\n".join(lines)


def _improve(client, ctx: Context, repo_dir, src, unit, base: Outcome, signal, make_prompt):
    out = base
    if not out.test_code:
        return out
    best, feedback = signal(repo_dir, src, unit, out.test_code)
    for _ in range(GUIDED_ROUNDS):
        if best >= 1.0 or not feedback:
            break
        reply = client.complete(SYSTEM, make_prompt(ctx.render(), out.test_code, feedback))
        out.tokens += reply.tokens
        out.calls += 1
        out.rounds += 1
        candidate = extract_tests(reply.text)
        if candidate is None:
            break
        fixed, _run = repair(client, ctx.render(), candidate, repo_dir, src, rounds=1)
        out.tokens += fixed.tokens
        out.calls += fixed.calls
        if not fixed.test_code:
            break
        score, new_feedback = signal(repo_dir, src, unit, fixed.test_code)
        if score <= best:
            break
        out.test_code, out.n_kept = fixed.test_code, count_tests(fixed.test_code)
        best, feedback = score, new_feedback
    return out


def _start(client, ctx, repo_dir, src, base: Outcome | None) -> Outcome:
    """The M1 result to improve. Pass the saved one so M2 and M3 start from identical tests."""
    if base is None:
        return modes.run_m1(client, ctx, repo_dir, src)
    return replace(base, history=list(base.history))  # never edit the caller's copy


def run_m2(client, ctx: Context, repo_dir: Path, src: str, unit: dict, base=None) -> Outcome:
    base = _start(client, ctx, repo_dir, src, base)
    return _improve(client, ctx, repo_dir, src, unit, base, _coverage_signal, coverage_prompt)


def run_m3(client, ctx: Context, repo_dir: Path, src: str, unit: dict, base=None) -> Outcome:
    base = _start(client, ctx, repo_dir, src, base)
    return _improve(client, ctx, repo_dir, src, unit, base, _mutation_signal, mutant_prompt)
