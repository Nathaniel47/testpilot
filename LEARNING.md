# LEARNING.md: TestPilot

Plain-English notes on what was built and why. One section per step.

## Step 1: Kickoff & plan

*Stub. Filled in as the project progresses.* Step 1 only produced the plan: PLAN.md (what to build and why), BUILD_STEPS.md (the 8 steps) and CLAUDE.md (working rules).

The one idea to hold on to: a test suite can have 100% line coverage and still catch almost no bugs, because coverage only shows that code *ran*, not that its results were *checked*. TestPilot measures the second thing by injecting small bugs (mutants) and counting how many the tests catch.

Concept readings to be expanded in later steps:
- Mutation testing: Papadakis et al., "Mutation Testing Advances: An Analysis and Survey" (2019).
- LLM test generation with repair: CoverUp (Altmayer Pizzorno & Berger, 2024) and Pynguin (Lukasczyk & Fraser, 2022).
- Sandboxing untrusted code: Python `subprocess` and `resource` docs.
