"""Choose a smaller set of units for runs that cannot cover a whole split.

Taking the first N units would cover only the first libraries in the file. Instead each library's
units are shuffled with a fixed seed and the libraries are interleaved in proportion to their
size. So any first N of that order is a random sample spread across libraries, a smaller subset
is always contained in a larger one, and every mode and LLM seed gets the same units.
"""

import random

SUBSET_SEED = 20240606


def spread_order(units: list[dict], seed: int = SUBSET_SEED) -> list[dict]:
    """All units, ordered so that every prefix is spread across libraries."""
    by_repo: dict[str, list[dict]] = {}
    for unit in units:
        by_repo.setdefault(unit["repo"], []).append(unit)
    keyed = []
    for repo in sorted(by_repo):
        # Seeded per library, and sorted first so the order of the input does not matter.
        rng = random.Random(f"{seed}:{repo}")
        members = sorted(by_repo[repo], key=lambda u: u["id"])
        rng.shuffle(members)
        offset = rng.random()
        for i, unit in enumerate(members):
            keyed.append(((i + offset) / len(members), repo, unit))
    return [unit for _, _, unit in sorted(keyed, key=lambda k: k[:2])]


def take_subset(units: list[dict], limit: int, seed: int = SUBSET_SEED) -> list[dict]:
    """`limit` units spread across libraries; 0 (or too large) means all, in the given order."""
    if not limit or limit >= len(units):
        return units
    return spread_order(units, seed)[:limit]
