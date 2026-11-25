"""Logic behind the demo page, kept free of UI code so it can be tested.

A visitor's function is checked, written into a throwaway package, and tested and scored by the
same pipeline as the study, inside the sandbox. Anything that could reach outside it is refused
before any code runs.
"""

import ast
import tempfile
import threading
import time
from pathlib import Path

from testpilot.check import check
from testpilot.ingest.parse import parse_repo

MAX_CHARS = 3000
MAX_LINES = 60
SAFE_IMPORTS = {
    "math", "re", "itertools", "functools", "collections", "string", "operator", "typing",
    "decimal", "fractions", "bisect", "heapq", "textwrap", "dataclasses",
}  # fmt: skip
PKG = "demo_pkg"
MODULE = "demo_mod"
RUN_LOCK = threading.Lock()  # one scoring job at a time keeps a free host responsive

EXAMPLES = {
    "clamp (number limits)": '''def clamp(value: int, low: int, high: int) -> int:
    """Limit value to the range [low, high].

    >>> clamp(5, 0, 3)
    3
    >>> clamp(-2, 0, 3)
    0
    """
    if value < low:
        return low
    if value > high:
        return high
    return value
''',
    "is_leap_year (date rule)": '''def is_leap_year(year: int) -> bool:
    """Gregorian leap year rule.

    >>> is_leap_year(2024)
    True
    >>> is_leap_year(1900)
    False
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
''',
    "fizzbuzz (strings)": '''def fizzbuzz(n: int) -> str:
    """Classic FizzBuzz for one number.

    >>> fizzbuzz(15)
    'FizzBuzz'
    >>> fizzbuzz(7)
    '7'
    """
    if n % 15 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)
''',
}


class Refused(ValueError):
    """The input cannot be analysed; the message is safe to show to the visitor."""


def validate(code: str) -> str:
    """Return the function's name, or raise Refused with a plain reason."""
    if not code.strip():
        raise Refused("Paste a Python function first.")
    if len(code) > MAX_CHARS or code.count("\n") > MAX_LINES:
        raise Refused(f"Too long: keep it under {MAX_LINES} lines and {MAX_CHARS} characters.")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise Refused(f"That is not valid Python: {exc.msg} (line {exc.lineno}).") from None
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1 or len(tree.body) != 1 + sum(isinstance(n, ast.Import | ast.ImportFrom)
                                                     for n in tree.body):  # fmt: skip
        raise Refused("Paste exactly one function (imports from the safe list are allowed).")
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]] if node.level == 0 else ["."]
        for name in names:
            if name not in SAFE_IMPORTS:
                raise Refused(
                    f"Import `{name}` is not allowed in the demo. Allowed: "
                    + ", ".join(sorted(SAFE_IMPORTS))
                    + "."
                )
    return funcs[0].name


def analyze(code: str, mode: str = "b0") -> dict:
    """Generate, run and score tests for one pasted function. Returns a result dict."""
    name = validate(code)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="demo_") as tmp:
        repo = Path(tmp)
        (repo / PKG).mkdir()
        (repo / PKG / "__init__.py").write_text("", encoding="utf-8")
        (repo / PKG / f"{MODULE}.py").write_text(code, encoding="utf-8")
        units = parse_repo(repo.name, repo, PKG)
        mine = [u for u in units if u.qualname == name]
        if not mine or mine[0].reasons:
            why = mine[0].reasons if mine else ["not found"]
            raise Refused(
                "This function is outside what the study can test reliably ("
                + ", ".join(why)
                + "). Try a pure function with a few branches that returns a value."
            )
        with RUN_LOCK:
            rows = check(repo, PKG, [f"{PKG}/{MODULE}.py"], mode=mode, max_units=1)
    if not rows:
        raise Refused("No testable function found.")
    row = rows[0]
    row["seconds"] = round(time.monotonic() - started, 1)
    return row
