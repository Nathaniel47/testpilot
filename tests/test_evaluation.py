import json

import pytest

from testpilot import evaluate
from testpilot.report import evaluation
from testpilot.report.tables import load_scores
from testpilot.score.batch import score_dir


def write_scores(work, mode, seed, rows):
    folder = work / "scores" / f"{mode}_s{seed}"
    folder.mkdir(parents=True)
    for i, row in enumerate(rows):
        (folder / f"{i}.json").write_text(json.dumps(row), encoding="utf-8")


def fake_row(uid, repo, line, mut):
    return {
        "unit_id": uid, "repo": repo, "has_tests": True, "line_cov": line, "branch_cov": line,
        "mutation_score": mut, "n_mutants": 10, "n_equivalent": 1, "tokens": 500,
    }  # fmt: skip


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTPILOT_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(evaluation, "RESULTS", tmp_path / "results")
    return tmp_path / "work"


@pytest.fixture
def units(monkeypatch):
    ids = [f"u{i}" for i in range(6)]
    data = {"units": [{"id": u, "split": "dev"} for u in ids]}
    real = evaluation.json.loads
    monkeypatch.setattr(
        evaluation.json, "loads", lambda s, *a, **k: data if '"units"' in s[:200] else real(s)
    )
    return ids


def test_report_has_only_modes_with_data_and_writes_charts(work, units, tmp_path):
    rows = [fake_row(u, "toolz" if i % 2 else "boltons", 0.9, 0.5) for i, u in enumerate(units)]
    write_scores(work, "b0", 0, rows)
    text = evaluation.build("dev", [0], ["b0", "m1", "m3"])
    out = tmp_path / "results"
    assert "B0" in text and "| M1 |" not in text and "| M3 |" not in text
    for name in ("evaluation.md", "limitations.md", "chart_gap_scatter.png"):
        assert (out / name).stat().st_size > 0
    assert "Modes without results yet" in (out / "limitations.md").read_text(encoding="utf-8")
    assert "Not run yet" in text


def test_seed_variance_appears_only_when_several_seeds_exist(work, units):
    for seed, mut in ((0, 0.4), (1, 0.6)):
        write_scores(work, "m1", seed, [fake_row(u, "toolz", 0.9, mut) for u in units])
    text = evaluation.build("dev", [0, 1], ["m1"])
    assert "seed 0: 0.400" in text and "seed 1: 0.600" in text and "Std dev" in text


def test_report_returns_none_without_scores(work, units):
    assert evaluation.build("dev", [0], ["m1"]) is None


def test_limitations_name_the_gaps_honestly(work, units):
    write_scores(work, "b0", 0, [fake_row(u, "toolz", 0.9, 0.5) for u in units])
    evaluation.build("dev", [0], ["b0"])
    text = (evaluation.RESULTS / "limitations.md").read_text(encoding="utf-8")
    for phrase in ("Memorisation", "Equivalent mutants", "mutmut cross-check has not been run"):
        assert phrase in text


def test_evaluate_stops_cleanly_when_budget_is_reached(monkeypatch):
    calls = []

    def fake_generate(argv):
        calls.append(argv)
        return 75

    monkeypatch.setattr(evaluate.generate_batch, "main", fake_generate)
    assert evaluate.main(["--modes", "m1", "m2"]) == 75
    assert len(calls) == 1  # did not go on to the next mode


def test_score_dirs_are_per_mode_and_seed(work):
    assert score_dir("m1", 0) != score_dir("m1", 1) != score_dir("m2", 1)
    assert load_scores(score_dir("m1", 0)) == {}


def test_modes_are_compared_on_the_same_units_only(work, units):
    write_scores(work, "b0", 0, [fake_row(u, "toolz", 0.5, 0.1) for u in units])
    write_scores(work, "m1", 0, [fake_row(u, "toolz", 1.0, 0.9) for u in units[:2]])
    text = evaluation.build("dev", [0], ["b0", "m1"])
    assert "Units compared: 2" in text and "B0 6, M1 2" in text
    assert "| B0 | 2 |" in text and "| M1 | 2 |" in text
