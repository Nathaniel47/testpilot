"""Generation modes. B0 template, M0 single shot, M1 generate plus repair.

M2 (coverage-guided) and M3 (mutation-guided) are added with scoring in later tasks. Every mode
returns the same `Outcome`, so scoring does not care which one made the tests.
"""

from pathlib import Path

from testpilot.context.builder import Context
from testpilot.generate.parse_response import extract_tests
from testpilot.generate.prompts import SYSTEM, generation_prompt
from testpilot.generate.template import generate_template_tests
from testpilot.repair.loop import Outcome, count_tests, finalize, repair
from testpilot.sandbox.pytest_run import run_tests


def run_b0(ctx: Context, repo_dir: Path, src: str) -> Outcome:
    """Offline template tests; failing drafts are dropped, no repair."""
    code = generate_template_tests(ctx.module, ctx.qualname, ctx.source)
    return _single(code, repo_dir, src)


def run_m0(client, ctx: Context, repo_dir: Path, src: str) -> Outcome:
    """One LLM call, no repair: failing tests are dropped."""
    reply = client.complete(SYSTEM, generation_prompt(ctx.render()))
    code = extract_tests(reply.text)
    if code is None:
        return Outcome(status="no_code", tokens=reply.tokens, calls=1)
    out = _single(code, repo_dir, src)
    out.tokens, out.calls = reply.tokens, 1
    return out


def run_m1(client, ctx: Context, repo_dir: Path, src: str) -> Outcome:
    """One LLM call, then up to 3 repair rounds on failures."""
    text = ctx.render()
    reply = client.complete(SYSTEM, generation_prompt(text))
    code = extract_tests(reply.text)
    if code is None:
        return Outcome(status="no_code", tokens=reply.tokens, calls=1)
    out, _ = repair(client, text, code, repo_dir, src)
    out.tokens += reply.tokens
    out.calls += 1
    return out


def _single(code: str, repo_dir: Path, src: str) -> Outcome:
    run = run_tests(repo_dir, src, code)
    out = Outcome(n_written=count_tests(code), history=[len(run.passed)])
    out.test_code = finalize(code, run)
    out.n_kept = count_tests(out.test_code) if out.test_code else 0
    out.n_dropped = out.n_written - out.n_kept
    out.status = "ok" if out.n_kept else "no_passing_tests"
    return out
