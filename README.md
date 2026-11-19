# TestPilot: LLM Unit-Test Generator with Mutation Scoring

Generates unit tests for real open-source Python projects with an LLM, repairs the ones that fail, and grades the result by how many injected bugs (mutants) the tests catch, not only by coverage. Compared against coverage-only generation.

**Status:** Step 3 of 8 (data pipeline). See [PLAN.md](PLAN.md) for the design and [BUILD_STEPS.md](BUILD_STEPS.md) for progress.

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

The "data" is 12 open-source Python libraries, fetched at pinned commits (`data/repos.json`) and only parsed in this step. Licences were detected from each repo's own LICENSE file and checked against the manifest by `python -m testpilot.ingest.build_dataset`, which stops if one is missing or not permissive. Each repo's own tests are set aside (`data/reference_tests/`, git-ignored) and used only as a human-written reference. The sample is 229 units (69 dev, 160 test), saved in `data/units.json`; see [results/data_report.md](results/data_report.md).

| Repo | Licence | Commit |
|---|---|---|
| [more-itertools](https://github.com/more-itertools/more-itertools) | MIT | `e3f79f4` |
| [toolz](https://github.com/pytoolz/toolz) | BSD-3-Clause | `451af60` |
| [boltons](https://github.com/mahmoud/boltons) | BSD-3-Clause | `d31d821` |
| [cachetools](https://github.com/tkem/cachetools) | MIT | `c5de513` |
| [python-slugify](https://github.com/un33k/python-slugify) | MIT | `4b6b5b4` |
| [humanize](https://github.com/python-humanize/humanize) | MIT | `a950045` |
| [tabulate](https://github.com/astanin/python-tabulate) | MIT | `268615a` |
| [semver](https://github.com/python-semver/python-semver) | BSD-3-Clause | `a4b7d33` |
| [sortedcontainers](https://github.com/grantjenks/python-sortedcontainers) | Apache-2.0 | `3ac3586` |
| [idna](https://github.com/kjd/idna) | BSD-3-Clause | `d357725` |
| [tomli](https://github.com/hukkin/tomli) | MIT | `43a86ad` |
| [packaging](https://github.com/pypa/packaging) | Apache-2.0 OR BSD-2-Clause | `cf2cdf0` |

Rebuild: `python -m testpilot.ingest.build_dataset` (needs network and git; the seed is in `data/repos.json`).

## Safety

Generated tests and target code run only in a sandbox (separate process, time and memory limits, empty environment, temporary folder; Docker in CI). Only open-source code and no real personal data are used.
