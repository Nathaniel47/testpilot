"""Prompt text. Kept in one place so a prompt change is one visible diff."""

SYSTEM = (
    "You write pytest unit tests for one Python function. Reply with exactly one ```python "
    "code block containing a complete test file and nothing else. Rules: import only the "
    "module under test, pytest and the standard library; no network, files, randomness or "
    "time; each test is a small function named test_*; assert exact expected values you can "
    "work out from the code, including edge cases and error branches; never mock the "
    "function under test."
)


def generation_prompt(ctx_text: str) -> str:
    return (
        f"{ctx_text}\nWrite a pytest file that tests the function under test. Cover every "
        "branch you can see. Only assert values you are sure about."
    )


def repair_prompt(ctx_text: str, test_code: str, failures: str) -> str:
    return (
        f"{ctx_text}\nThese tests were written for the function under test:\n"
        f"```python\n{test_code}\n```\nWhen run against the real code they failed:\n"
        f"```\n{failures}\n```\nThe function is correct and the tests are wrong. Fix or remove "
        "the failing tests. Reply with the full corrected test file in one ```python block."
    )


def mutant_prompt(ctx_text: str, test_code: str, survivors: str) -> str:
    return (
        f"{ctx_text}\nExisting passing tests:\n```python\n{test_code}\n```\nThese deliberate "
        f"bugs (mutants) were NOT caught by the tests:\n{survivors}\nAdd tests that pass on the "
        "real code but would fail on each bug. Reply with the full test file in one ```python "
        "block."
    )


def coverage_prompt(ctx_text: str, test_code: str, missing: str) -> str:
    return (
        f"{ctx_text}\nExisting passing tests:\n```python\n{test_code}\n```\nThese lines of the "
        f"function under test are never executed: {missing}\nAdd tests that reach them. Reply "
        "with the full test file in one ```python block."
    )
