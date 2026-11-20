# Data report

Seed 20240606. Built by `python -m testpilot.ingest.build_dataset`. Repo code runs only inside the sandbox, and only to import modules (the runnable check).

## Totals

- Repos: 12, source lines: 76,715
- Functions and methods found: 2,378; eligible after static filters: 508 (21%)
- Sampled units: 228 (dev 68, test 160)
- Kinds: classmethod 5, function 179, method 43, staticmethod 1
- Unit length (lines): median 19.0, min 4, max 59
- Mutation-site count per unit: median 4.0, min 2, max 37
- With docstring: 74%
- Context size (estimated tokens): median 478.5, max 1818; units where optional context was dropped to fit the cap: 0; with helpers: 114; with callers: 148

## Per repo

| Repo | Licence (detected) | Src lines | Functions | Eligible | Sampled | Dev | Test |
|---|---|---:|---:|---:|---:|---:|---:|
| more-itertools | MIT | 7,290 | 260 | 95 | 30 | 9 | 21 |
| toolz | BSD-3-Clause | 3,805 | 150 | 43 | 30 | 9 | 21 |
| boltons | BSD-3-Clause | 17,718 | 886 | 184 | 30 | 9 | 21 |
| cachetools | MIT | 1,682 | 176 | 14 | 14 | 4 | 10 |
| python-slugify | MIT | 620 | 16 | 4 | 4 | 1 | 3 |
| humanize | MIT | 1,737 | 37 | 4 | 4 | 1 | 3 |
| tabulate | MIT | 3,130 | 73 | 36 | 30 | 9 | 21 |
| semver | BSD-3-Clause | 1,635 | 67 | 15 | 12 | 4 | 8 |
| sortedcontainers | Apache-2.0 | 4,043 | 127 | 23 | 8 | 2 | 6 |
| idna | BSD-3-Clause | 20,428 | 47 | 14 | 14 | 4 | 10 |
| tomli | MIT | 938 | 39 | 23 | 23 | 7 | 16 |
| packaging | Apache-2.0 + BSD-2-Clause | 13,689 | 500 | 53 | 29 | 9 | 20 |

## Why functions were filtered out

A function can have several reasons, so counts add up to more than the total.

| Reason | Functions |
|---|---:|
| not_public | 1,153 |
| few_mutation_sites | 998 |
| too_short | 515 |
| no_return_value | 396 |
| property_or_abstract | 124 |
| too_long | 103 |
| io_or_nondeterministic | 95 |
| nested_function | 59 |
| not_implemented | 13 |
| skipped_module | 7 |
| module_not_importable | 1 |

## Sample records

- `more-itertools:more_itertools/more.py:always_iterable` (function, lines 2134-2184, 3 branches, 7 mutation sites, split test)
- `toolz:toolz/recipes.py:countby` (function, lines 8-23, 1 branches, 2 mutation sites, split test)
- `tabulate:tabulate/__init__.py:_align_cell_veritically` (function, lines 2547-2557, 2 branches, 17 mutation sites, split test)
- `idna:idna/core.py:valid_contexto` (function, lines 393-439, 15 branches, 37 mutation sites, split test)

## Quality problems found

- Fewer than 30 eligible units: cachetools (14), python-slugify (4), humanize (4), semver (12), sortedcontainers (8), idna (14), tomli (23), packaging (29).
- sortedcontainers: every sampled unit is a method.
- Eligibility is decided statically. A unit can still fail to run alone (needs a constructed object, a fixture, or a helper); Step 4's sandbox run measures this and units that cannot be run are replaced from `data/reserve.json` (the other eligible units, in seeded order).
- Banned-name filtering is by name, so it is conservative: a function that uses a local variable called `time` is dropped, and an indirect call to a clock is not caught.
- Popular libraries may be in the LLM's training data, which can inflate scores. Step 6 measures how often generated tests reproduce the removed reference tests.
