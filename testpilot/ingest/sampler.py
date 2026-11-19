"""Seeded, reproducible sampling and the dev/test split."""

import random

from testpilot.ingest.parse import Unit


def sample_units(units: list[Unit], n: int, max_methods: int, seed: int, repo: str) -> list[Unit]:
    """Pick up to n eligible units from one repo, at most max_methods of them methods."""
    eligible = sorted((u for u in units if not u.reasons), key=lambda u: u.id)
    random.Random(f"{seed}:{repo}:sample").shuffle(eligible)
    picked: list[Unit] = []
    methods = 0
    for unit in eligible:
        if len(picked) == n:
            break
        if unit.kind != "function":
            if methods == max_methods:
                continue
            methods += 1
        picked.append(unit)
    return sorted(picked, key=lambda u: u.id)


def split_dev_test(units: list[Unit], dev_fraction: float, seed: int, repo: str) -> dict[str, str]:
    """Map unit id to 'dev' or 'test', stratified per repo."""
    ids = sorted(u.id for u in units)
    random.Random(f"{seed}:{repo}:split").shuffle(ids)
    n_dev = round(len(ids) * dev_fraction)
    return {uid: ("dev" if i < n_dev else "test") for i, uid in enumerate(ids)}
