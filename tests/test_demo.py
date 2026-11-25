import pytest

from app import gradio_app
from app.build_space import build_space
from app.demo_core import EXAMPLES, MAX_CHARS, Refused, analyze, validate


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


def test_space_folder_has_what_the_host_needs_and_nothing_secret(tmp_path):
    files = build_space(tmp_path / "space")
    assert {"README.md", "app.py", "requirements.txt", "app/gradio_app.py"} <= set(files)
    assert not any(f.endswith((".env", ".pyc")) or "llm_cache" in f for f in files)
    assert "sdk: gradio" in (tmp_path / "space" / "README.md").read_text(encoding="utf-8")
