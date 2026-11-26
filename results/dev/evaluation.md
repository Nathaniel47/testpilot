# Evaluation (dev split)

Scoring is fully automatic (tests run in the sandbox; no LLM judge). Primary metric: **mutation
score**, the share of injected bugs the tests catch. Modes are ranked on bugs held out from
generation. Line and branch coverage are reported beside it, because the project's question is how
far coverage overstates test quality.

Modes with scored units here: B0 offline template (baseline), M0 single LLM call, M1 + repair, M2 coverage-guided (the coverage-only comparison), M3 mutation-guided.
Modes without data are left out, not estimated.

**Units compared: 68**, the ones scored in every listed mode (scored so far per mode:
B0 68, M0 68, M1 68, M2 68, M3 68). Modes are compared on identical
units so an easier set of units cannot flatter one of them.

## Results

Values are means with 95% bootstrap intervals over units.

| Mode | Units | With tests | Line cov | Branch cov | Unseen-bug score | All-bug score | Cov - all-bug gap | Tokens/unit | Tokens/killed mutant |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 68 | 65 | 0.41 [0.32, 0.49] | 0.30 [0.20, 0.39] | 0.25 [0.17, 0.34] | 0.26 [0.17, 0.35] | +0.15 | 0 | 0 |
| M0 | 68 | 60 | 0.85 [0.77, 0.93] | 0.94 [0.89, 0.98] | 0.79 [0.70, 0.87] | 0.80 [0.71, 0.87] | +0.06 | 1516 | 177 |
| M1 | 68 | 67 | 0.97 [0.94, 0.99] | 0.98 [0.96, 0.99] | 0.91 [0.86, 0.95] | 0.91 [0.87, 0.94] | +0.06 | 3092 | 296 |
| M2 | 68 | 67 | 0.98 [0.94, 1.00] | 0.98 [0.97, 0.99] | 0.91 [0.86, 0.95] | 0.91 [0.87, 0.95] | +0.07 | 3523 | 335 |
| M3 | 68 | 67 | 0.97 [0.94, 0.99] | 0.98 [0.96, 0.99] | 0.91 [0.86, 0.95] | 0.92 [0.88, 0.96] | +0.05 | 4242 | 403 |

M3 minus M1 on the same units (positive = mutation-guided is better): unseen-bug score no difference on any of 68 units, line coverage no difference on any of 68 units.

M3 minus M2 on the same units (positive = mutation-guided is better): unseen-bug score -0.002 [-0.004, +0.000] (higher on 0, lower on 2, n=68), line coverage -0.005 [-0.012, -0.000] (higher on 0, lower on 4, n=68).

**Room to improve:** M1 already catches every unseen bug on 47 of 68 units, so only 21 could score higher with guidance.

**Compare modes on the unseen-bug score.** Each function's mutants are split in two by a fixed
seed. Mutation-guided generation (M3) is shown survivors from one half only and decides what to
keep using that half only. The unseen-bug score counts the other half, which no mode was told
about. The all-bug score includes the half M3 saw, so it favours M3: it is listed for
completeness and for the coverage gap, not for ranking M3.

![coverage vs mutation score](chart_coverage_vs_mutation.png)

![per-unit gap](chart_gap_scatter.png)

![by library](chart_per_repo.png)

## By library (mean unseen-bug score)

| Library | B0 | M0 | M1 | M2 | M3 |
|---|---|---|---|---|---|
| boltons | 0.27 (n=9) | 0.80 (n=9) | 0.86 (n=9) | 0.86 (n=9) | 0.86 (n=9) |
| cachetools | 0.08 (n=4) | 0.95 (n=4) | 0.95 (n=4) | 0.95 (n=4) | 0.95 (n=4) |
| humanize | 0.00 (n=1) | 0.00 (n=1) | 1.00 (n=1) | 1.00 (n=1) | 1.00 (n=1) |
| idna | 0.03 (n=4) | 0.61 (n=4) | 0.81 (n=4) | 0.82 (n=4) | 0.81 (n=4) |
| more-itertools | 0.75 (n=9) | 0.93 (n=9) | 0.93 (n=9) | 0.93 (n=9) | 0.93 (n=9) |
| packaging | 0.06 (n=9) | 0.67 (n=9) | 0.99 (n=9) | 0.99 (n=9) | 0.99 (n=9) |
| python-slugify | 0.00 (n=1) | 0.45 (n=1) | 0.60 (n=1) | 0.60 (n=1) | 0.60 (n=1) |
| semver | 0.15 (n=4) | 0.74 (n=4) | 0.74 (n=4) | 0.74 (n=4) | 0.74 (n=4) |
| sortedcontainers | 0.70 (n=2) | 0.80 (n=2) | 0.80 (n=2) | 0.80 (n=2) | 0.80 (n=2) |
| tabulate | 0.26 (n=9) | 1.00 (n=9) | 1.00 (n=9) | 1.00 (n=9) | 1.00 (n=9) |
| tomli | 0.00 (n=7) | 0.45 (n=7) | 0.80 (n=7) | 0.81 (n=7) | 0.80 (n=7) |
| toolz | 0.27 (n=9) | 1.00 (n=9) | 1.00 (n=9) | 1.00 (n=9) | 1.00 (n=9) |

## Variance over seeds

Not run yet: no mode has more than one seed scored.

## Counts

- B0: 68 units scored, 3 with no passing test, 779 mutants of which 0 flagged likely-equivalent. 423 held out; 4 mutant runs retried after a timeout, 2 counted as caught by timeout, 1 by the memory limit.
- M0: 68 units scored, 8 with no passing test, 670 mutants of which 0 flagged likely-equivalent. 423 held out; 4 mutant runs retried after a timeout, 3 counted as caught by timeout, 1 by the memory limit.
- M1: 68 units scored, 1 with no passing test, 798 mutants of which 0 flagged likely-equivalent. 423 held out; 4 mutant runs retried after a timeout, 3 counted as caught by timeout, 1 by the memory limit.
- M2: 68 units scored, 1 with no passing test, 798 mutants of which 0 flagged likely-equivalent. 423 held out; 6 mutant runs retried after a timeout, 5 counted as caught by timeout, 1 by the memory limit.
- M3: 68 units scored, 1 with no passing test, 798 mutants of which 0 flagged likely-equivalent. 423 held out; 4 mutant runs retried after a timeout, 3 counted as caught by timeout, 1 by the memory limit.

## How to reproduce

```
python -m testpilot.evaluate --modes b0 m0 m1 m2 m3 --split dev --seeds 0
python -m testpilot.cli report --split dev --modes b0 m0 m1 m2 m3 --seeds 0
```

See limitations.md for what these numbers do not show.
