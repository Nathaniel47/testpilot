"""Build results/evaluation.md, results/limitations.md and the charts from saved scores.

Only modes that really have scored units appear. Nothing is filled in or estimated.
"""

import json

from testpilot import config
from testpilot.report import charts
from testpilot.report.tables import comparison_markdown, load_scores, mean
from testpilot.score.batch import score_dir

RESULTS = config.ROOT / "results"
DATA = config.ROOT / "data"
ALL_MODES = ["b0", "m0", "m1", "m2", "m3"]
NAMES = {
    "b0": "B0 offline template (baseline)",
    "m0": "M0 single LLM call",
    "m1": "M1 + repair",
    "m2": "M2 coverage-guided (the coverage-only comparison)",
    "m3": "M3 mutation-guided",
}


def split_filter(rows: dict[str, dict], split: str, unit_split: dict[str, str]) -> dict[str, dict]:
    return {k: r for k, r in rows.items() if split == "all" or unit_split.get(k) == split}


def seed_table(modes: list[str], seeds: list[int], split: str, unit_split: dict) -> str:
    """Mean mutation score per seed for modes that have more than one seed scored."""
    lines = []
    for mode in modes:
        per_seed = []
        for s in seeds:
            rows = split_filter(load_scores(score_dir(mode, s)), split, unit_split)
            vals = [
                r["mutation_score"] for r in rows.values() if r.get("mutation_score") is not None
            ]
            if vals:
                per_seed.append((s, mean(vals), len(vals)))
        if len(per_seed) > 1:
            means = [m for _, m, _ in per_seed]
            mu = sum(means) / len(means)
            sd = (sum((m - mu) ** 2 for m in means) / (len(means) - 1)) ** 0.5
            cells = ", ".join(f"seed {s}: {m:.3f} (n={n})" for s, m, n in per_seed)
            lines.append(f"| {mode.upper()} | {cells} | {mu:.3f} | {sd:.3f} |")
    if not lines:
        return (
            "Not run yet: no mode has more than one seed scored. LLM modes need an API key; "
            "see the run commands below.\n"
        )
    return (
        "| Mode | Mutation score per seed | Mean | Std dev over seeds |\n|---|---|---|---|\n"
        + "\n".join(lines)
        + "\n"
    )


def repo_table(scores: dict[str, dict]) -> str:
    repos = sorted({r.get("repo", "?") for rows in scores.values() for r in rows.values()})
    head = "| Library | " + " | ".join(m.upper() for m in scores) + " |\n"
    head += "|---|" + "---|" * len(scores) + "\n"
    body = ""
    for repo in repos:
        cells = []
        for rows in scores.values():
            v = [r["mutation_score"] for r in rows.values()
                 if r.get("repo") == repo and r.get("mutation_score") is not None]  # fmt: skip
            cells.append(f"{mean(v):.2f} (n={len(v)})" if v else "-")
        body += f"| {repo} | " + " | ".join(cells) + " |\n"
    return head + body


def facts(scores: dict[str, dict]) -> str:
    out = []
    for mode, rows in scores.items():
        rs = list(rows.values())
        mutants = sum(r.get("n_mutants", 0) for r in rs)
        equiv = sum(r.get("n_equivalent", 0) for r in rs)
        none = sum(not r.get("has_tests") for r in rs)
        out.append(
            f"- {mode.upper()}: {len(rs)} units scored, {none} with no passing test, "
            f"{mutants} mutants of which {equiv} flagged likely-equivalent."
        )
    return "\n".join(out)


def build(split: str = "dev", seeds: list[int] | None = None, modes: list[str] | None = None):
    seeds = seeds or [0]
    modes = modes or ALL_MODES
    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))["units"]
    unit_split = {u["id"]: u["split"] for u in units}
    scores = {}
    for m in modes:
        rows = split_filter(load_scores(score_dir(m, seeds[0])), split, unit_split)
        if rows:
            scores[m] = rows
    if not scores:
        return None
    # Compare modes on the same units only: otherwise a mode scored on easier units looks better.
    common = set.intersection(*(set(rows) for rows in scores.values()))
    available = {m: len(rows) for m, rows in scores.items()}
    scores = {m: {u: r for u, r in rows.items() if u in common} for m, rows in scores.items()}
    if not common:
        return None
    RESULTS.mkdir(exist_ok=True)
    charts.coverage_vs_mutation_bars(scores, RESULTS / "chart_coverage_vs_mutation.png")
    gap_mode = "m3" if "m3" in scores else next(iter(scores))
    charts.gap_scatter(scores[gap_mode], gap_mode, RESULTS / "chart_gap_scatter.png")
    charts.per_repo_dots(scores, RESULTS / "chart_per_repo.png")

    text = f"""# Evaluation ({split} split)

Scoring is fully automatic (tests run in the sandbox; no LLM judge). Primary metric: **mutation
score**, the share of injected bugs the tests catch. Line and branch coverage are reported beside
it, because the project's question is how far coverage overstates test quality.

Modes with scored units here: {", ".join(NAMES[m] for m in scores)}.
Modes without data are left out, not estimated.

**Units compared: {len(common)}**, the ones scored in every listed mode (scored so far per mode:
{", ".join(f"{m.upper()} {n}" for m, n in available.items())}). Modes are compared on identical
units so an easier set of units cannot flatter one of them.

## Results

{comparison_markdown(scores, seeds[0])}
![coverage vs mutation score](chart_coverage_vs_mutation.png)

![per-unit gap](chart_gap_scatter.png)

![by library](chart_per_repo.png)

## By library (mean mutation score)

{repo_table(scores)}
## Variance over seeds

{seed_table(modes, seeds, split, unit_split)}
## Counts

{facts(scores)}

## How to reproduce

```
python -m testpilot.evaluate --modes b0 m1 m2 m3 --split dev --seeds 0 1 2
python -m testpilot.cli report
```

See limitations.md for what these numbers do not show.
"""
    (RESULTS / "evaluation.md").write_text(text, encoding="utf-8")
    (RESULTS / "limitations.md").write_text(limitations(scores), encoding="utf-8")
    return text


def limitations(scores: dict[str, dict]) -> str:
    missing = [NAMES[m] for m in ALL_MODES if m not in scores]
    gaps = (
        "**Modes without results yet:** " + "; ".join(missing) + ". Any claim about them would "
        "be a guess.\n\n"
        if missing
        else ""
    )
    return (
        "# Limitations\n\n"
        + gaps
        + """## Where the results are weak

- **Small sample, wide intervals.** The full set is 228 functions from 12 libraries (68 dev, 160
  test), fewer than the 300 first planned. Bootstrap intervals over about 70 units are wide, so
  small differences between modes are not evidence. Results use the dev split unless stated;
  prompts were tuned on dev only, and the test split should be run once at the end.
- **Memorisation.** The libraries are popular and public, so the model may have seen their code
  and tests in training. Moving the repo's own tests out of the working copy stops copying from
  the prompt, not from memory. Scores may be inflated for the best-known libraries.
- **Mutation score is an estimate.** The engine is our own and has a small operator set (no
  statement deletion, no exception-type changes, no loop edits). At most 40 mutants are sampled
  per function. Equivalent mutants cannot be removed automatically, so every score is a lower
  bound on the true detection rate. The optional "likely equivalent" flag (a mutant that also
  survives the repo's own tests) is a heuristic that can wrongly drop real survivors when the
  reference suite is weak, and it is slow, so it is off unless `--flag-equivalent` is given. Check
  the counts section: if no mutants are flagged, scores are not corrected at all. The planned
  mutmut cross-check has not been run.
- **Ceiling effect.** Functions are small and get only a handful of mutants each (see the counts
  section), so per-function scores are coarse. If an LLM mode scores close to 1.0, the mutant set
  is too easy to tell stronger modes apart, and differences between M1, M2 and M3 will be hidden.
  A larger operator set (statement deletion, boundary and exception mutations) or more mutants
  per function would be needed to separate them.
- **Template baseline is generous to itself.** B0 drafts that fail are dropped before scoring, so
  its score reflects only tests that already pass. The baseline is weak by design, not a strong
  competitor.
- **One model family, one temperature.** Only Groq's `openai/gpt-oss-120b` at temperature 0 was
  planned for the main runs. The Gemini confirmation run has not been done, and its model ID is
  unverified. Free-tier token limits (about 200K a day) cap how many units and seeds can run.
- **Seeds.** Variance over seeds is only measured where several seeds were actually run (a small
  subset). With temperature 0 and cached calls, a "seed" mostly changes sampling of mutants, so
  seed variance understates real model variance.
- **Missing comparisons.** B1 (the library's own human tests, scored per function) and B2
  (Pynguin) are not yet scored, so there is no human-test yardstick in the table.
- **Sandbox.** Process limits and soft guards stop accidents, not a determined attacker; Docker in
  CI is the hard boundary and was not run locally.
- **Python only**, deterministic pure functions only. Results say nothing about code that uses
  files, time, randomness, the network, or large objects, which is much of real code.

## What would improve them

More libraries and units (or a pooled run across all 228 on the test split), several real LLM
seeds, a second model family, the mutmut cross-check in Docker, B1 and B2 on a subset, and a hand
review of a sample of survivors to measure how many are truly equivalent.
"""
    )
