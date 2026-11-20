"""Failure-feedback loop.

Rule: a test that fails on the unmodified code is a bad test, never a bug found. So failures
are sent back to the model as "the code is right, fix the test", at most MAX_ROUNDS times.
Tests that still fail are dropped (and counted); only tests that passed are kept.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path

from testpilot.generate.parse_response import extract_tests
from testpilot.generate.prompts import SYSTEM, repair_prompt
from testpilot.sandbox.pytest_run import TestRun, run_tests

MAX_ROUNDS = 3


@dataclass
class Outcome:
    test_code: str = ""  # final file: passing tests only ("" if none survived)
    n_written: int = 0  # test functions in the first draft
    n_kept: int = 0
    n_dropped: int = 0
    rounds: int = 0
    tokens: int = 0
    calls: int = 0
    status: str = "ok"  # ok | no_code | no_passing_tests
    history: list[int] = field(default_factory=list)  # passing count after each round


def keep_only(code: str, names: list[str]) -> str:
    """Return `code` with every test function removed except those in `names`."""
    tree = ast.parse(code)
    drop = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test") and n.name not in names
    ]
    lines = code.splitlines()
    for node in sorted(drop, key=lambda n: -n.lineno):
        first = min([node.lineno] + [d.lineno for d in node.decorator_list])
        del lines[first - 1 : node.end_lineno]
    return "\n".join(lines).rstrip() + "\n"


def count_tests(code: str) -> int:
    return sum(
        1
        for n in ast.walk(ast.parse(code))
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test")
    )


def finalize(code: str, run: TestRun) -> str:
    """Drop failing tests; return "" when nothing passed."""
    if run.error or not run.passed:
        return ""
    return keep_only(code, [n.split("[")[0] for n in run.passed]) if run.failed else code


def repair(client, ctx_text: str, code: str, repo_dir: Path, src: str, rounds: int = MAX_ROUNDS):
    """Run `code`, ask for fixes while tests fail, return (Outcome, last TestRun)."""
    out = Outcome(n_written=count_tests(code))
    run = run_tests(repo_dir, src, code)
    out.history.append(len(run.passed))
    while not run.all_passed and out.rounds < rounds:
        reply = client.complete(SYSTEM, repair_prompt(ctx_text, code, run.failure_text()))
        out.rounds += 1
        out.calls += 1
        out.tokens += reply.tokens
        fixed = extract_tests(reply.text)
        if fixed is None or fixed == code:
            break
        code = fixed
        run = run_tests(repo_dir, src, code)
        out.history.append(len(run.passed))
    out.test_code = finalize(code, run)
    kept = count_tests(out.test_code) if out.test_code else 0
    out.n_kept = kept
    out.n_dropped = max(out.n_written - kept, 0)
    out.status = "ok" if kept else "no_passing_tests"
    return out, run
