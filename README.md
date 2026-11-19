# TestPilot: LLM Unit-Test Generator with Mutation Scoring

Generates unit tests for real open-source Python projects with an LLM, repairs the ones that fail, and grades the result by how many injected bugs (mutants) the tests catch, not only by coverage. Compared against coverage-only generation.

**Status:** Step 2 of 8 (repo setup). See [PLAN.md](PLAN.md) for the design and [BUILD_STEPS.md](BUILD_STEPS.md) for progress.

**Demo / results / architecture:** added in later steps (see PLAN.md for the planned architecture).

## Run locally

Requires Python 3.11.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env   # then fill in the keys you have
pytest
python -m testpilot.cli --version
```

macOS / Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill in the keys you have
pytest
python -m testpilot.cli --version
```

Docker (locked down: read-only filesystem, no capabilities):

```bash
docker compose build
docker compose run --rm testpilot --version
```

Optional: `pre-commit install` enables ruff and a gitleaks secret scan on every commit.

## Configuration

Keys come only from environment variables (see `.env.example`): `TESTPILOT_GROQ_API_KEY`, `TESTPILOT_GEMINI_API_KEY`. Without keys, the offline template generator still works (from Step 5).

## Datasets and licences

Target repos and their licences are recorded in Step 3.

## Safety

Generated tests and target code run only in a sandbox (separate process, time and memory limits, empty environment, temporary folder; Docker in CI). Only open-source code and no real personal data are used.
