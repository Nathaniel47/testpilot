"""Three charts for the evaluation. Colours are colour-blind safe and every chart is labelled."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from testpilot.score.stats import bootstrap_ci, mean  # noqa: E402

LINE, MUT = "#7f7f7f", "#0072B2"  # grey = coverage, blue = mutation score


def _vals(rows, key):
    return [r[key] for r in rows.values() if r.get(key) is not None]


def _err(values, seed):
    m, ci = mean(values), bootstrap_ci(values, seed)
    return (m, (m - ci[0], ci[1] - m)) if ci else (m, (0, 0))


def coverage_vs_mutation_bars(scores: dict[str, dict], path: Path, seed: int = 0) -> None:
    """Chart 1: per mode, mean line coverage next to mean mutation score (95% interval)."""
    fig, ax = plt.subplots(figsize=(7, 4))
    modes = list(scores)
    for offset, key, colour, label in ((-0.2, "line_cov", LINE, "Line coverage"),
                                       (0.2, "mutation_score", MUT, "Mutation score")):  # fmt: skip
        pts = [
            _err(_vals(scores[m], key), seed) if _vals(scores[m], key) else (0, (0, 0))
            for m in modes
        ]
        xs = [i + offset for i in range(len(modes))]
        ax.bar(xs, [p[0] for p in pts], 0.4, color=colour, label=label,
               yerr=[[p[1][0] for p in pts], [p[1][1] for p in pts]], capsize=3)  # fmt: skip
    ax.set_xticks(range(len(modes)), [m.upper() for m in modes])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Mean over units (1.0 = all)")
    ax.set_title("Line coverage and mutation score by mode")
    ax.legend(frameon=False)
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


def per_repo_dots(scores: dict[str, dict], path: Path) -> None:
    """Chart 3: mean mutation score per library and mode, to show where results are weak."""
    repos = sorted({r.get("repo", "?") for rows in scores.values() for r in rows.values()})
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, (mode, rows) in enumerate(scores.items()):
        xs, ys = [], []
        for j, repo in enumerate(repos):
            v = [r["mutation_score"] for r in rows.values()
                 if r.get("repo") == repo and r.get("mutation_score") is not None]  # fmt: skip
            if v:
                xs.append(mean(v))
                ys.append(j)
        ax.scatter(xs, ys, color=palette[i % len(palette)], label=mode.upper(), s=40)
    ax.set_yticks(range(len(repos)), repos)
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Mean mutation score")
    ax.set_title("Mutation score by library")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
