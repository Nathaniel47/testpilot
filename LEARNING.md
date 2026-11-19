# LEARNING.md: TestPilot

Plain-English notes on what was built and why. One section per step.

## Step 1: Kickoff & plan

*Stub. Filled in as the project progresses.* Step 1 only produced the plan: PLAN.md (what to build and why), BUILD_STEPS.md (the 8 steps) and CLAUDE.md (working rules).

The one idea to hold on to: a test suite can have 100% line coverage and still catch almost no bugs, because coverage only shows that code *ran*, not that its results were *checked*. TestPilot measures the second thing by injecting small bugs (mutants) and counting how many the tests catch.

Concept readings to be expanded in later steps:
- Mutation testing: Papadakis et al., "Mutation Testing Advances: An Analysis and Survey" (2019).
- LLM test generation with repair: CoverUp (Altmayer Pizzorno & Berger, 2024) and Pynguin (Lukasczyk & Fraser, 2022).
- Sandboxing untrusted code: Python `subprocess` and `resource` docs.

## Step 2: Repo setup

- **Package layout**: only `testpilot/` with `config.py` and a stub `cli.py` exist so far. The other folders in PLAN.md (ingest, generate, mutation, ...) are added in the step that needs them, so nothing is an empty placeholder.
- **`config.py`**: every setting comes from a `TESTPILOT_*` environment variable, and unprefixed variables are ignored on purpose, so a stray `GEMINI_API_KEY` on the machine is never picked up by accident. A test also checks that `.env.example` holds names only, with empty values.
- **Dependencies**: `requirements.txt` holds what the tool needs at run time, including `pytest` and `coverage`, because the sandbox runs them on the generated tests. `requirements-dev.txt` adds ruff, pre-commit and matplotlib. There is no mutation library: the plan uses an own small engine, with mutmut added later and only in Docker/CI.
- **Docker**: non-root user, read-only filesystem, no Linux capabilities, no privilege escalation, 2 GB memory. Generated tests are untrusted code, so CI runs the test suite inside this locked-down container as a second layer behind the sandbox. The image build is not run locally, so the first check is the CI `docker` job.
- **CI**: GitHub Actions runs ruff (lint and format check) and pytest on every push, plus the Docker job.
- **pre-commit**: ruff plus a gitleaks scan, so a pasted API key is blocked before it reaches a public repo.

How to check: `ruff check .`, `ruff format --check .` and `pytest` should all pass (6 tests). `python -m testpilot.cli --version` prints the version.

## Step 3: Data pipeline

- **What the "data" is.** Not a dataset file but 12 real open-source libraries, each fetched at one exact commit (`data/repos.json`). Pinning means the code under test never changes underneath the results. Nothing from these repos is run in this step: files are only read and parsed with Python's `ast` module, which turns source text into a tree without executing it.
- **Licences.** The build script reads each repo's LICENSE file, recognises MIT, BSD or Apache-2.0 by their standard wording, compares with what the manifest claims, and stops if one does not match or is not permissive. This matters because we copy and run the code and publish results about it.
- **Setting the repo's tests aside.** Each repo's own tests are moved to `data/reference_tests/` (git-ignored). The LLM must not see them, or it could copy them. They come back later only as the human-written yardstick. Toolz keeps tests *inside* its package, so the script also searches the source tree for them. Reading: any intro to data leakage in ML evaluation, e.g. the scikit-learn "common pitfalls" guide.
- **Function inventory and filters** (`ingest/parse.py`): 2,378 functions and methods were found; 509 (21%) pass static filters. A unit is dropped if it is private, async, a property, nested, 3 or fewer lines, over 60 lines, has no return value, has fewer than 2 places a bug could be injected, or touches the clock, randomness, files, network or `sys`. The point is to keep units that are deterministic and can be tested alone, so a failing test means a bad test, not a flaky environment. Tabulate keeps nearly all its logic in underscore-prefixed helpers, so it is the one repo where private functions are allowed.
- **Seeded sample and split** (`ingest/sampler.py`): up to 30 units per repo, at most 8 of them methods (methods need an object built first, which is harder to test). The 30/70 dev/test split is made per repo, so every repo appears in both. Tune prompts on dev only; report on test only, otherwise the numbers flatter the tool. `data/reserve.json` lists the other eligible units in seeded order, as replacements for any unit that turns out not to run alone in Step 4.
- **Result:** 229 units (69 dev, 160 test), fewer than the 300 first planned, because the small libraries simply do not have 30 eligible functions (python-slugify has 4, humanize 5). The report states this and the plan was updated. Because there are fewer units, results will have wider error bars, which Step 6 reports.

How to check: `python -m testpilot.ingest.build_dataset` (needs network and git) rebuilds `data/units.json`, `data/repo_facts.json`, `data/reserve.json` and `results/data_report.md`; running it twice gives the same files. Then `pytest` (14 tests, including checks that the saved dataset has no duplicate ids and no test files).
