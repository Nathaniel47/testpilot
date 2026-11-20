import ast

import pytest

from testpilot.mutation.mutate import make_mutants
from testpilot.mutation.operators import apply_site, find_sites
from testpilot.mutation.runner import score_tests

LIB = '''
def clamp(x, lo, hi):
    """Limit x."""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def pad(n):
    return n + 0
'''
STRONG = (
    "from pkg.lib import clamp\n\n\ndef test_a():\n    assert clamp(-5, 0, 10) == 0\n"
    "    assert clamp(15, 0, 10) == 10\n    assert clamp(5, 0, 10) == 5\n"
    "    assert clamp(0, 0, 10) == 0\n    assert clamp(10, 0, 10) == 10\n"
)
WEAK = "from pkg.lib import clamp\n\n\ndef test_a():\n    assert clamp(5, 0, 10) == 5\n"


def func(src):
    return ast.parse(src).body[0]


def test_sites_cover_compare_return_and_condition():
    ops = {s.operator for s in find_sites(func(LIB))}
    assert {"compare", "return", "condition"} <= ops


def test_docstring_is_never_mutated():
    sites = find_sites(func('def f():\n    """doc"""\n    return 1\n'))
    assert [s.operator for s in sites] == ["return", "constant"]


def test_each_mutant_differs_from_original_by_one_site():
    original = func(LIB)
    base = ast.unparse(original)
    for site in find_sites(original):
        assert ast.unparse(apply_site(original, site.index)) != base


def test_sampling_is_seeded_and_capped():
    big = "def f(x):\n" + "".join(f"    x = x + {i}\n" for i in range(30)) + "    return x\n"
    a = make_mutants(big, "f", "k", seed=1, limit=10)
    b = make_mutants(big, "f", "k", seed=1, limit=10)
    c = make_mutants(big, "f", "k", seed=2, limit=10)
    assert len(a) == 10 and [m.id for m in a] == [m.id for m in b]
    assert [m.id for m in a] != [m.id for m in c]


@pytest.fixture
def repo(tmp_path):
    pkg = tmp_path / "repo" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "lib.py").write_text(LIB)
    return tmp_path / "repo"


UNIT = {"file": "pkg/lib.py", "qualname": "clamp", "sha256": "abc"}


def test_strong_tests_kill_more_mutants_than_weak_tests(repo):
    strong = score_tests(repo, "pkg", UNIT, STRONG)
    weak = score_tests(repo, "pkg", UNIT, WEAK)
    assert strong.ok and weak.ok and strong.total == weak.total > 5
    assert weak.score < strong.score
    # The two boundary mutants (< to <=, > to >=) return the same value, so they cannot be killed.
    survivors = {r.detail for r in strong.results if not r.killed}
    assert survivors == {"< -> <=", "> -> >="}


def test_tests_that_fail_on_original_code_are_not_scored(repo):
    bad = WEAK.replace("== 5", "== 6")
    report = score_tests(repo, "pkg", UNIT, bad)
    assert not report.ok and report.score is None


def test_survivors_of_the_reference_suite_are_flagged_equivalent(repo, tmp_path):
    ref = tmp_path / "ref"
    ref.mkdir()
    (ref / "test_ref.py").write_text(STRONG.replace("test_a", "test_ref"))
    plain = score_tests(repo, "pkg", UNIT, WEAK)
    flagged = score_tests(repo, "pkg", UNIT, WEAK, reference_dir=ref)
    survivors = plain.total - plain.killed
    assert survivors > 0
    assert flagged.scored <= plain.scored
    assert flagged.score <= plain.score + 1e-9 or flagged.scored < plain.scored
