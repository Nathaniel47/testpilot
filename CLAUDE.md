# CLAUDE.md: TestPilot coding rules

- Follow PLAN.md; if anything conflicts, PLAN.md wins. Work one BUILD_STEPS.md step at a time.
- Python 3.11, no LangChain/LlamaIndex/LangGraph. Keep ingestion, generation, repair, mutation and reporting as separate plain modules.
- Secrets only from environment variables named `TESTPILOT_*`. Never commit `.env`; `.env.example` has names with empty values.
- Target repos are open-source code only, cloned at pinned commits. Generated tests and target code run only inside the sandbox (subprocess with time and memory limits, temp working directory, empty environment, no network; Docker in CI). Never run them directly in the project environment. No real personal data.
- Scoring is automatic (test pass/fail, line and branch coverage, mutation score). No LLM judge.
- Every LLM call goes through the cached client in `testpilot/llm/`. Fixed seeds; record model IDs, temperature, seed and git commit in `results/run_meta.json`.
- Format and lint with ruff (line length 100). Write tests in `tests/` for every feature; run `pytest` before each commit.
- Code comments only for non-obvious reasons. Plain-English explanations go in LEARNING.md, not chat.
- Commit with the step name in the message, then push (once a remote exists). Never add attribution to commits or PRs: no `Co-Authored-By` lines and no "Generated with" text.
