from types import SimpleNamespace

from testpilot.generate import guided
from testpilot.mutation import runner
from testpilot.mutation.mutate import Mutant, shown_ids


def mutants(n, same_description=()):
    return [
        Mutant(f"k#{i}", "op", 1 if i in same_description else i + 10, "d", f"code{i}")
        for i in range(n)
    ]


def test_split_is_seeded_and_gives_each_half_about_the_same():
    ms = mutants(11)
    shown = shown_ids(ms, "k")
    assert shown == shown_ids(ms, "k") and len(shown) == 5
    assert shown != shown_ids(ms, "other")


def test_a_single_mutant_is_held_out_not_shown():
    assert shown_ids(mutants(1), "k") == set()


def test_mutants_with_the_same_description_stay_in_one_half():
    for key in "abcdefgh":
        shown = shown_ids(mutants(8, same_description=(0, 1, 2)), key)
        assert len(shown & {"k#0", "k#1", "k#2"}) in (0, 3)


def result(shown, killed):
    return runner.MutantResult("i", "op", 1, "d", killed, shown=shown)


def test_unseen_score_ignores_shown_mutants():
    report = runner.MutationReport(
        ok=True, results=[result(True, True), result(False, True), result(False, False)]
    )
    assert report.unseen_score == 0.5 and report.score == 2 / 3
    assert runner.MutationReport(ok=True, results=[result(True, True)]).unseen_score is None


def test_m3_feedback_only_asks_for_the_shown_half(monkeypatch):
    seen = {}

    def fake_score(*args, **kwargs):
        seen.update(kwargs)
        return runner.MutationReport(ok=True, results=[result(True, False)])

    monkeypatch.setattr(guided, "score_tests", fake_score)
    guided._mutation_signal(None, "pkg", {}, "code")
    assert seen == {"shown_only": True}


LIB = """def sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
"""


def make_repo(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "lib.py").write_text(LIB)
    return {"file": "pkg/lib.py", "qualname": "sign", "sha256": "s1"}


def test_shown_only_never_runs_a_held_out_mutant(tmp_path):
    unit = make_repo(tmp_path)
    tests = "from pkg.lib import sign\n\n\ndef test_a():\n    assert sign(5) == 1\n"
    full = runner.score_tests(tmp_path, "pkg", unit, tests)
    part = runner.score_tests(tmp_path, "pkg", unit, tests, shown_only=True)
    assert {r.id for r in part.results} == {r.id for r in full.results if r.shown}
    assert 0 < len(part.results) < len(full.results)
    assert all(r.reason == "tests" for r in full.results if r.killed)


def fake_sandbox_runs(monkeypatch, outcomes):
    timeouts = []

    def fake_run(sb, timeout):
        timeouts.append(timeout)
        ok, timed_out = outcomes[min(len(timeouts) - 1, len(outcomes) - 1)]
        return SimpleNamespace(ok=ok, timed_out=timed_out, memory_exceeded=False, seconds=1.0)

    monkeypatch.setattr(runner, "_run", fake_run)
    return timeouts


def test_a_one_off_timeout_is_retried_and_not_counted_as_caught(tmp_path, monkeypatch):
    unit = make_repo(tmp_path)
    # Baseline passes; the first mutant times out once, then passes; the rest pass.
    timeouts = fake_sandbox_runs(monkeypatch, [(True, False), (False, True), (True, False)])
    report = runner.score_tests(tmp_path, "pkg", unit, "x")
    first = report.results[0]
    assert first.retried and not first.killed and first.reason == ""
    assert timeouts[2] == timeouts[1] * runner.RETRY_FACTOR
    assert not any(r.retried for r in report.results[1:])


def test_a_repeated_timeout_counts_as_caught_and_is_labelled(tmp_path, monkeypatch):
    unit = make_repo(tmp_path)
    fake_sandbox_runs(monkeypatch, [(True, False), (False, True)])
    report = runner.score_tests(tmp_path, "pkg", unit, "x")
    assert all(r.killed and r.retried and r.reason == "timeout" for r in report.results)
