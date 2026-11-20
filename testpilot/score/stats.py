"""Small statistics helpers: mean and a seeded bootstrap confidence interval."""

import random


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def bootstrap_ci(
    values: list[float], seed: int = 0, n_boot: int = 2000, level: float = 0.95
) -> tuple[float, float] | None:
    """Percentile bootstrap interval for the mean, resampling units with replacement."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    k = len(values)
    means = sorted(sum(rng.choices(values, k=k)) / k for _ in range(n_boot))
    lo = means[int((1 - level) / 2 * n_boot)]
    hi = means[int((1 + level) / 2 * n_boot) - 1]
    return lo, hi
