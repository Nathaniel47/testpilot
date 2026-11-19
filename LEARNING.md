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
