import pytest

from testpilot.context.builder import RepoIndex, build_context
from testpilot.generate import modes
from testpilot.generate.parse_response import extract_tests
from testpilot.generate.template import generate_template_tests
from testpilot.llm.budget import Budget
from testpilot.llm.cache import Cache
from testpilot.llm.client import LLMClient
from testpilot.llm.providers import Completion
from testpilot.repair.loop import keep_only
from testpilot.sandbox.pytest_run import run_tests

LIB = '''
def add(a: int, b: int) -> int:
    """Add.

    >>> add(1, 2)
    3
    >>> add(0, 0)
    0
    """
    return a + b


def sign(x):
    if x > 0:
        return 1
    return -1 if x < 0 else 0
'''

GOOD = (
    "```python\nfrom pkg.lib import sign\n\n\ndef test_pos():\n    assert sign(5) == 1\n\n\n"
    "def test_neg():\n    assert sign(-5) == -1\n```"
)
BAD_ONE = GOOD.replace("== -1", "== 7")


@pytest.fixture
def repo(tmp_path):
    pkg = tmp_path / "repo" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "lib.py").write_text(LIB)
    return tmp_path / "repo"


def ctx_for(repo, qual):
    unit = {"id": qual, "file": "pkg/lib.py", "qualname": qual, "kind": "function"}
    return build_context(unit, RepoIndex(repo, "pkg"))


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


def test_extract_tests_handles_fences_and_garbage():
    assert "def test_a" in extract_tests("hi\n```python\ndef test_a():\n    pass\n```\nbye")
    assert extract_tests("```python\ndef test_a(:\n```") is None
    assert extract_tests("no code here at all") is None
    assert extract_tests("```python\ndef helper():\n    pass\n```") is None
    assert "def test_cut" in extract_tests("```python\ndef test_cut():\n    assert 1\n")


def test_keep_only_removes_named_tests():
    code = "import pytest\n\n\ndef test_a():\n    assert 1\n\n\ndef test_b():\n    assert 0\n"
    out = keep_only(code, ["test_a"])
    assert "test_a" in out and "test_b" not in out and "import pytest" in out


def test_template_uses_docstring_examples_and_passes(repo):
    ctx = ctx_for(repo, "add")
    code = generate_template_tests(ctx.module, ctx.qualname, ctx.source)
    assert "docstring_examples" in code and "smoke" in code
    run = run_tests(repo, "pkg", code)
    assert run.all_passed and len(run.passed) >= 2


def test_b0_is_deterministic_and_runs_offline(repo):
    ctx = ctx_for(repo, "add")
    a, b = modes.run_b0(ctx, repo, "pkg"), modes.run_b0(ctx, repo, "pkg")
    assert a.test_code == b.test_code and a.status == "ok" and a.calls == 0


def test_run_tests_reports_failures_and_collection_errors(repo):
    bad = "from pkg.lib import sign\n\n\ndef test_x():\n    assert sign(1) == 2\n"
    run = run_tests(repo, "pkg", bad)
    assert "test_x" in run.failed and not run.all_passed
    broken = run_tests(repo, "pkg", "import nothing_here\n\n\ndef test_x():\n    pass\n")
    assert broken.error and not broken.passed


def test_m0_drops_failing_tests_without_repair(repo, tmp_path):
    client, calls = fake_client(tmp_path, [BAD_ONE])
    out = modes.run_m0(client, ctx_for(repo, "sign"), repo, "pkg")
    assert (out.n_written, out.n_kept, out.n_dropped, out.rounds) == (2, 1, 1, 0)
    assert "test_neg" not in out.test_code and len(calls) == 1


def test_m1_repairs_a_wrong_test_using_the_failure_message(repo, tmp_path):
    client, calls = fake_client(tmp_path, [BAD_ONE, GOOD])
    out = modes.run_m1(client, ctx_for(repo, "sign"), repo, "pkg")
    assert (out.n_kept, out.n_dropped, out.rounds, out.calls) == (2, 0, 1, 2)
    assert "assert" in calls[1] and "test_neg" in calls[1]
    assert out.history == [1, 2]


def test_m1_gives_up_after_three_rounds_and_keeps_passing_tests(repo, tmp_path):
    variants = [BAD_ONE.replace("== 7", f"== {n}") for n in (7, 8, 9, 10)]
    client, calls = fake_client(tmp_path, variants)
    out = modes.run_m1(client, ctx_for(repo, "sign"), repo, "pkg")
    assert out.rounds == 3 and len(calls) == 4
    assert out.n_kept == 1 and out.status == "ok"


def test_unusable_reply_is_counted_not_crashed(repo, tmp_path):
    client, _ = fake_client(tmp_path, ["sorry, I cannot help"])
    out = modes.run_m1(client, ctx_for(repo, "sign"), repo, "pkg")
    assert out.status == "no_code" and out.test_code == ""


def test_failure_text_has_no_random_temp_path():
    from testpilot.sandbox.pytest_run import TestRun

    err = r"File C:\Temp\testpilot_ab12cd34\code\test_generated.py:3: Error"
    other = err.replace("ab12cd34", "zz99yy88")
    assert TestRun(error=err).failure_text() == TestRun(error=other).failure_text()
    assert "testpilot_" not in TestRun(error=err).failure_text()
