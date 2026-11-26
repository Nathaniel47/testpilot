import json
from dataclasses import asdict

from testpilot.generate import batch, guided
from testpilot.repair.loop import Outcome
from testpilot.sandbox.pytest_run import TestRun

UNIT = {"id": "u", "split": "dev", "sha256": "abc"}


def test_memory_addresses_do_not_change_the_repair_prompt():
    a = TestRun(failed={"test_x": "assert <A object at 0x000001F78B064810> == 1"})
    b = TestRun(failed={"test_x": "assert <A object at 0x7f3a9c1d2e40> == 1"})
    assert a.failure_text() == b.failure_text()


def test_short_hex_values_in_assertions_are_kept():
    assert "0xff" in TestRun(failed={"t": "assert 0xff == 254"}).failure_text()


def test_saved_m1_outcome_is_used_without_running_m1_again(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTPILOT_WORK_DIR", str(tmp_path))
    saved = Outcome(test_code="def test_a(): pass", tokens=7, calls=2, history=[1])
    folder = tmp_path / "outcomes" / "m1_s3"
    folder.mkdir(parents=True)
    record = {"unit_id": "u", "split": "dev", **asdict(saved)}
    (folder / "abc.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(batch.modes, "run_m1", lambda *a: (_ for _ in ()).throw(AssertionError()))
    assert batch.m1_base(None, None, None, "pkg", UNIT, 3) == saved


def test_missing_m1_outcome_is_made_once_and_then_shared(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTPILOT_WORK_DIR", str(tmp_path))
    calls = []

    def fake_m1(*_):
        calls.append(1)
        return Outcome(test_code=f"# run {len(calls)}", calls=1)

    monkeypatch.setattr(batch.modes, "run_m1", fake_m1)
    for_m2 = batch.m1_base(None, None, None, "pkg", UNIT, 0)
    for_m3 = batch.m1_base(None, None, None, "pkg", UNIT, 0)
    assert for_m2 == for_m3 and len(calls) == 1


def test_guided_mode_does_not_edit_the_callers_base(monkeypatch):
    base = Outcome(test_code="x", history=[1])
    copy = guided._start(None, None, None, "pkg", base)
    copy.tokens += 5
    copy.history.append(2)
    assert base.tokens == 0 and base.history == [1]
