"""Offline, deterministic test generator (baseline B0). No API calls.

Two sources, strongest first: examples written in the docstring (doctest style), and a smoke
call built from type hints and defaults. Candidates are only drafts: the runner drops any that
fail on the original code, exactly as it does for LLM tests.
"""

import ast
import doctest

HINT_VALUES = {
    "int": ["2", "0", "-3"],
    "float": ["1.5", "0.0"],
    "str": ["'abc'", "''"],
    "bool": ["True", "False"],
    "bytes": ["b'ab'"],
    "list": ["[1, 2, 3]", "[]"],
    "tuple": ["(1, 2)"],
    "dict": ["{'a': 1}"],
    "set": ["{1, 2}"],
}
MAX_SMOKE = 4


def _hint_name(annotation) -> str | None:
    if annotation is None:
        return None
    base = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    return base.id if isinstance(base, ast.Name) else None


def _expr(src: str) -> str:
    """Re-render an expression so trailing comments cannot swallow the closing bracket."""
    return ast.unparse(ast.parse(src, mode="eval"))


def _valid(tests: list[str]) -> list[str]:
    ok = []
    for test in tests:
        try:
            ast.parse(test)
            ok.append(test)
        except SyntaxError:
            pass
    return ok


def _doctest_tests(doc: str, names_hint: str) -> list[str]:
    tests = []
    parts = doctest.DocTestParser().get_examples(doc)
    # One test per contiguous docstring: later examples may use earlier assignments.
    if not parts:
        return tests
    body = []
    for ex in parts:
        src = ex.source.strip()
        try:
            ast.parse(src, mode="eval")
            is_expr = True
        except SyntaxError:
            is_expr = False
        if ex.exc_msg:
            body.append("with pytest.raises(Exception):")
            body += ["    " + line for line in src.splitlines()]
        elif is_expr and ex.want.strip():
            body.append(f"assert repr({_expr(src)}) == {ex.want.strip()!r}")
        else:
            body += src.splitlines()
    tests.append(
        f"def test_{names_hint}_docstring_examples():\n" + "\n".join("    " + line for line in body)
    )
    return tests


def _smoke_tests(node: ast.FunctionDef, qualname: str) -> list[str]:
    args = node.args
    positional = args.posonlyargs + args.args
    if positional and positional[0].arg in ("self", "cls"):
        return []
    n_defaults = len(args.defaults)
    required = positional[: len(positional) - n_defaults]
    choices = []
    for arg in required:
        values = HINT_VALUES.get(_hint_name(arg.annotation))
        if not values:
            return []
        choices.append(values)
    tests = []
    for i in range(min(MAX_SMOKE, max((len(c) for c in choices), default=1))):
        call_args = ", ".join(c[min(i, len(c) - 1)] for c in choices)
        ret = _hint_name(node.returns)
        check = f"    assert isinstance(result, {ret})\n" if ret in HINT_VALUES else ""
        check = check or "    assert True" + chr(10)
        head = f"def test_{node.name}_smoke_{i}():" + chr(10)
        tests.append(head + f"    result = {node.name}({call_args})" + chr(10) + check)
    return tests


def generate_template_tests(module: str, qualname: str, source: str) -> str:
    """Return a pytest file for one unit, built only from its source text."""
    # "if 1:" accepts any indentation, even when docstring lines sit at column 0.
    if source[:1].isspace():
        node = ast.parse("if 1:" + chr(10) + source).body[0].body[0]
    else:
        node = ast.parse(source).body[0]
    doc = ast.get_docstring(node) or ""
    safe = qualname.replace(".", "_")
    tests = _valid(_doctest_tests(doc, safe))
    if "." not in qualname:
        tests += _valid(_smoke_tests(node, qualname))
    head = (
        "import pytest\n"
        f"import {module} as _mod\n\n"
        "globals().update({k: v for k, v in vars(_mod).items() if not k.startswith('__')})\n\n\n"
    )
    if not tests:
        tests = [f"def test_{safe}_is_callable():\n    assert callable({qualname.split('.')[0]})"]
    return head + "\n\n".join(tests) + "\n"
