import json

import pytest

from app.build_static import RESULTS, build_space
from testpilot.demo import page as gradio_app
from testpilot.demo.core import EXAMPLES, MAX_CHARS, Refused, analyze, validate


@pytest.mark.parametrize(
    "code, fragment",
    [
        ("", "Paste a Python function"),
        ("def f(:\n  pass", "not valid Python"),
        ("def f():\n    return 1\n\ndef g():\n    return 2\n", "exactly one function"),
        ("import os\n\ndef f():\n    return os.getcwd()\n", "Import `os` is not allowed"),
        ("from subprocess import run\n\ndef f():\n    return run\n", "not allowed"),
        ("x = 1\n\ndef f():\n    return x\n", "exactly one function"),
        ("def f():\n    return '" + "a" * MAX_CHARS + "'\n", "Too long"),
    ],
)
def test_unsafe_or_wrong_input_is_refused_before_anything_runs(code, fragment):
    with pytest.raises(Refused, match=fragment):
        validate(code)


def test_safe_import_and_every_example_validate():
    assert validate("import math\n\ndef f(x):\n    return math.sqrt(x)\n") == "f"
    for code in EXAMPLES.values():
        validate(code)


def test_function_the_study_cannot_test_gets_a_plain_reason():
    code = "def f(x):\n    return x\n"
    with pytest.raises(Refused, match="outside what the study can test"):
        analyze(code)


def test_analyze_scores_an_example_end_to_end():
    row = analyze(EXAMPLES["clamp (number limits)"])
    assert row["has_tests"] and "def test_" in row["test_code"]
    assert 0 <= row["mutation_score"] <= 1 and row["n_mutants"] > 3
    assert row["seconds"] > 0


def test_one_click_run_returns_scores_and_tests():
    report, tests, session = gradio_app.run(EXAMPLES["clamp (number limits)"], None)
    assert "Mutation score" in report and "def test_" in tests and session["runs"] == 1


def test_cooldown_and_session_cap_block_without_running_anything(monkeypatch):
    monkeypatch.setattr(gradio_app, "analyze", lambda code: pytest.fail("must not run"))
    soon, tests, _ = gradio_app.run("x", {"runs": 1, "last": 100.0}, now=lambda: 105.0)
    assert "Please wait 15s" in soon and tests == ""
    capped = {"runs": gradio_app.MAX_RUNS_PER_SESSION, "last": 0.0}
    assert "limit reached" in gradio_app.run("x", capped)[0]


def test_refused_input_is_explained_on_the_page():
    code = chr(10).join(["import os", "", "def f():", "    return os.sep"])
    report, tests, _ = gradio_app.run(code, None)
    assert "Cannot analyse" in report and tests == ""


def test_page_builds_and_exposes_no_public_api():
    demo = gradio_app.build()
    assert all(fn.api_visibility == "private" for fn in demo.fns.values())


def test_static_space_is_two_files_pinned_to_one_commit(tmp_path):
    sha = "a" * 40
    assert build_space(tmp_path / "space", commit=sha) == ["README.md", "index.html"]
    html = (tmp_path / "space" / "index.html").read_text(encoding="utf-8")
    assert f"@{sha}/app/static/page.js" in html
    assert "sdk: static" in (tmp_path / "space" / "README.md").read_text(encoding="utf-8")


def test_saved_results_match_the_current_examples():
    saved = json.loads(RESULTS.read_text(encoding="utf-8"))["examples"]
    assert [(r["name"], r["code"]) for r in saved] == list(EXAMPLES.items())
    for row in saved:
        assert "def test_" in row["test_code"] and 0 <= row["mutation_score"] <= 1


def test_saved_scores_are_what_the_pipeline_produces_now():
    saved = json.loads(RESULTS.read_text(encoding="utf-8"))["examples"][0]
    live = analyze(saved["code"])
    for key in ("line_cov", "mutation_score", "n_mutants", "survivors", "test_code"):
        assert live[key] == saved[key]


def test_page_never_treats_data_as_html():
    script = (RESULTS.parent / "page.js").read_text(encoding="utf-8")
    for risky in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert risky not in script


def test_every_subpackage_is_part_of_the_install():
    from setuptools import find_packages

    found = set(find_packages(include=["testpilot*"]))
    assert {"testpilot.demo", "testpilot.sandbox", "testpilot.mutation"} <= found
