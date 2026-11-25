import json
from collections import Counter

from testpilot import config
from testpilot.subset import spread_order, take_subset


def dataset(split):
    data = json.loads((config.ROOT / "data" / "units.json").read_text(encoding="utf-8"))
    return [u for u in data["units"] if u["split"] == split]


def test_subset_is_repeatable_and_ignores_input_order():
    units = dataset("test")
    a = [u["id"] for u in take_subset(units, 30)]
    assert a == [u["id"] for u in take_subset(units, 30)]
    assert a == [u["id"] for u in take_subset(list(reversed(units)), 30)]
    assert len(set(a)) == 30


def test_smaller_subsets_sit_inside_larger_ones():
    units = dataset("test")
    assert take_subset(units, 120)[:30] == take_subset(units, 30)


def test_subset_covers_libraries_in_proportion():
    for split, limit in (("dev", 30), ("test", 30), ("test", 120)):
        units = dataset(split)
        total = Counter(u["repo"] for u in units)
        got = Counter(u["repo"] for u in take_subset(units, limit))
        for repo, n in total.items():
            assert abs(got[repo] - limit * n / len(units)) <= 1.5, (split, limit, repo)


def test_no_limit_or_a_large_one_means_every_unit():
    units = dataset("dev")
    assert take_subset(units, 0) == units and take_subset(units, 999) == units
    assert sorted(u["id"] for u in spread_order(units)) == sorted(u["id"] for u in units)
