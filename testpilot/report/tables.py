"""Comparison table across modes, with bootstrap confidence intervals over units."""

import json
from pathlib import Path

from testpilot.score.stats import bootstrap_ci, mean


def load_scores(folder: Path) -> dict[str, dict]:
    rows = {}
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            rows[row["unit_id"]] = row
    return rows


def _fmt(values: list[float], seed: int) -> str:
    m = mean(values)
    if m is None:
        return "n/a"
    ci = bootstrap_ci(values, seed)
    return f"{m:.2f} [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else f"{m:.2f}"


def _vals(rows, key):
    return [r[key] for r in rows if r.get(key) is not None]


def mode_summary(rows: list[dict], seed: int = 0) -> dict:
    killed = sum((r.get("mutation_score") or 0) * r.get("n_mutants", 0) for r in rows)
    tokens = sum(r.get("tokens", 0) for r in rows)
    line, mut = mean(_vals(rows, "line_cov")), mean(_vals(rows, "mutation_score"))
    return {
        "units": len(rows),
        "with_tests": sum(bool(r.get("has_tests")) for r in rows),
        "line": _fmt(_vals(rows, "line_cov"), seed),
        "branch": _fmt(_vals(rows, "branch_cov"), seed),
        "mutation": _fmt(_vals(rows, "mutation_score"), seed),
        "gap": "n/a" if line is None or mut is None else f"{line - mut:+.2f}",
        "tokens_per_unit": f"{tokens / len(rows):.0f}" if rows else "n/a",
        "tokens_per_kill": f"{tokens / killed:.0f}" if killed else "n/a",
    }


def paired_difference(a: dict, b: dict, key: str, seed: int = 0) -> str:
    """Mean of (b - a) over units both modes scored, with a bootstrap interval."""
    diffs = [
        b[u][key] - a[u][key]
        for u in a.keys() & b.keys()
        if a[u].get(key) is not None and b[u].get(key) is not None
    ]
    return f"{_fmt(diffs, seed)} (n={len(diffs)})" if diffs else "n/a"


def comparison_markdown(scores: dict[str, dict[str, dict]], seed: int = 0) -> str:
    head = (
        "| Mode | Units | With tests | Line cov | Branch cov | Mutation score | "
        "Cov - mutation gap | Tokens/unit | Tokens/killed mutant |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    body = ""
    for mode, rows in scores.items():
        s = mode_summary(list(rows.values()), seed)
        body += (
            f"| {mode.upper()} | {s['units']} | {s['with_tests']} | {s['line']} | {s['branch']} "
            f"| {s['mutation']} | {s['gap']} | {s['tokens_per_unit']} | {s['tokens_per_kill']} |\n"
        )
    text = "Values are means with 95% bootstrap intervals over units.\n\n" + head + body
    if "m2" in scores and "m3" in scores:
        m2, m3 = scores["m2"], scores["m3"]
        text += (
            "\nM3 minus M2 on the same units (positive = mutation-guided is better): "
            f"mutation score {paired_difference(m2, m3, 'mutation_score', seed)}, "
            f"line coverage {paired_difference(m2, m3, 'line_cov', seed)}.\n"
        )
    return text
