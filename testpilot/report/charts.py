"""Three charts for the evaluation. Colours are colour-blind safe and every chart is labelled."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from testpilot.score.stats import bootstrap_ci, mean  # noqa: E402

LINE, MUT = "#7f7f7f", "#0072B2"  # grey = coverage, blue = mutation score (all bugs)
UNSEEN = "#E69F00"


def _vals(rows, key):
    return [r[key] for r in rows.values() if r.get(key) is not None]


def _err(values, seed):
    m, ci = mean(values), bootstrap_ci(values, seed)
    return (m, (m - ci[0], ci[1] - m)) if ci else (m, (0, 0))


def coverage_vs_mutation_bars(scores: dict[str, dict], path: Path, seed: int = 0) -> None:
    """Chart 1: per mode, mean line coverage next to the mutation scores (95% interval)."""
    fig, ax = plt.subplots(figsize=(7, 4))
    modes = list(scores)
    series = [("line_cov", LINE, "Line coverage"), ("mutation_score", MUT, "All-bug score")]
    if all("unseen_score" in r for rows in scores.values() for r in rows.values()):
        series.append(("unseen_score", UNSEEN, "Unseen-bug score"))
    width = 0.8 / len(series)
    for n, (key, colour, label) in enumerate(series):
        offset = (n - (len(series) - 1) / 2) * width
        pts = [
            _err(_vals(scores[m], key), seed) if _vals(scores[m], key) else (0, (0, 0))
            for m in modes
        ]
        xs = [i + offset for i in range(len(modes))]
        ax.bar(xs, [p[0] for p in pts], width, color=colour, label=label,
               yerr=[[p[1][0] for p in pts], [p[1][1] for p in pts]], capsize=3)  # fmt: skip
    ax.set_xticks(range(len(modes)), [m.upper() for m in modes])
    ax.set_ylim(0, 1.18)  # room above the tallest bar for the legend
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Mean over units (1.0 = all)")
    ax.set_title("Line coverage and mutation scores by mode")
    ax.legend(frameon=False, loc="upper center", ncol=len(series))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def gap_scatter(rows: dict[str, dict], mode: str, path: Path) -> None:
    """Chart 2: one dot per unit. Dots below the diagonal run the code but miss bugs."""
    pts = [
        (r["line_cov"], r["mutation_score"])
        for r in rows.values()
        if r.get("line_cov") is not None and r.get("mutation_score") is not None
    ]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], color=LINE, lw=1, ls="--", label="coverage = mutation score")
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=MUT, alpha=0.5, s=22)
    ax.set_xlabel("Line coverage of the unit")
    ax.set_ylabel("Mutation score of the unit")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_title(f"{mode.upper()}: each dot is one function (n={len(pts)})")
    ax.legend(frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def per_repo_dots(scores: dict[str, dict], path: Path, key: str = "mutation_score") -> None:
    """Chart 3: mean score per library and mode, to show where results are weak."""
    name = "unseen-bug score" if key == "unseen_score" else "mutation score"
    repos = sorted({r.get("repo", "?") for rows in scores.values() for r in rows.values()})
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
    fig, ax = plt.subplots(figsize=(7.5, 6))
    step = 0.7 / max(len(scores), 1)
    for i, (mode, rows) in enumerate(scores.items()):
        xs, ys = [], []
        for j, repo in enumerate(repos):
            v = [r[key] for r in rows.values()
                 if r.get("repo") == repo and r.get(key) is not None]  # fmt: skip
            if v:
                xs.append(mean(v))
                # Offset each mode, or equal scores hide one another.
                ys.append(j + (i - (len(scores) - 1) / 2) * step)
        ax.scatter(xs, ys, color=palette[i % len(palette)], label=mode.upper(), s=22)
    ax.set_yticks(range(len(repos)), repos)
    for j in range(len(repos) - 1):
        ax.axhline(j + 0.5, color=LINE, lw=0.5, alpha=0.3)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel(f"Mean {name}")
    ax.set_title(f"{name.capitalize()} by library")
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
