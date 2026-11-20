import pytest

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


def test_page_runs_an_example_with_one_click():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=180).run()
    assert not at.exception
    at.selectbox[0].select("clamp (number limits)").run()
    at.button[0].click().run()
    assert not at.exception and not at.error
    labels = [m.label for m in at.metric]
    assert "Mutation score" in labels and "Line coverage" in labels
    assert any("def test_" in c.value for c in at.code)
