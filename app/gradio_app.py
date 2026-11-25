"""TestPilot demo: paste or pick a Python function; see tests, coverage and mutation score.

Run locally:  python -m app.gradio_app
Uses the offline template generator, so it needs no key. LLM tests are not offered here; the
study results are in results/evaluation.md.
"""

import time

import gradio as gr

from app.demo_core import EXAMPLES, Refused, analyze

MAX_RUNS_PER_SESSION = 8
COOLDOWN_SECONDS = 20
NO_TESTS = "# no passing tests were produced"

INTRO = """# TestPilot: do the tests catch bugs, or just run the code?
Pick an example or paste one Python function. TestPilot writes tests for it, runs them in a
sandbox, then injects small bugs (mutants) and counts how many the tests catch. Coverage says a
line ran; mutation score says a wrong line would be noticed. A run takes about 10 to 60 seconds."""

FOOTER = """This demo uses the offline template generator, which is a weak baseline. In the study,
an LLM with repair reached a mean mutation score of 0.90 on 61 dev-split functions, against 0.29
for this baseline. Code runs with time and memory limits. The app does not save what you paste."""


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def summary(row: dict) -> str:
    cov, mut = row.get("line_cov"), row.get("mutation_score")
    text = (
        "| Line coverage | Mutation score | Mutants tried | Time |\n|---|---|---|---|\n"
        f"| {_pct(cov)} | {_pct(mut)} | {row.get('n_mutants', 0)} | {row.get('seconds', 0)} s |\n"
    )
    if cov is not None and mut is not None and cov - mut > 0.05:
        text += (
            f"\n**Gap of {cov - mut:.0%}:** these tests run {cov:.0%} of the lines but catch only "
            f"{mut:.0%} of the injected bugs."
        )
    if row.get("survivors"):
        text += "\n\n### Bugs the tests missed\n\n| Line | Change | Kind |\n|---|---|---|\n"
        text += "".join(
            f"| {s['line']} | `{s['detail']}` | {s['operator']} |\n" for s in row["survivors"]
        )
        text += (
            "\nSome of these may be harmless edits that do not change behaviour (equivalent "
            "mutants), so the score is a lower bound."
        )
    return text


def run(code: str, session: dict | None, now=time.time):
    """Return (summary markdown, test code, session state). Enforces the per-session limits."""
    session = dict(session or {"runs": 0, "last": 0.0})
    wait = COOLDOWN_SECONDS - (now() - session["last"])
    if session["runs"] >= MAX_RUNS_PER_SESSION:
        return "Demo limit reached for this session. Reload the page to continue.", "", session
    if wait > 0:
        return f"Please wait {wait:.0f}s before the next run (this demo is shared).", "", session
    session = {"runs": session["runs"] + 1, "last": now()}
    try:
        row = analyze(code or "")
    except Refused as exc:
        return f"**Cannot analyse this:** {exc}", "", session
    return summary(row), row.get("test_code") or NO_TESTS, session


def load_example(name: str) -> str:
    return EXAMPLES.get(name, "")


def build() -> gr.Blocks:
    first = next(iter(EXAMPLES))
    with gr.Blocks(title="TestPilot demo", analytics_enabled=False) as demo:
        gr.Markdown(INTRO)
        session = gr.State(None)
        choice = gr.Dropdown(list(EXAMPLES), value=first, label="Example")
        code = gr.Code(value=EXAMPLES[first], language="python", label="Function to test")
        go = gr.Button("Generate and score tests", variant="primary")
        result = gr.Markdown()
        tests = gr.Code(language="python", label="Generated tests", interactive=False)
        gr.Markdown(FOOTER)
        choice.change(load_example, choice, code, api_visibility="private")
        # One run at a time across all visitors; no public API, so limits cannot be skipped.
        go.click(
            run_event,
            [code, session],
            [result, tests, session],
            concurrency_limit=1,
            api_visibility="private",
        )
    return demo.queue(max_size=10)


def run_event(code: str, session: dict | None):
    return run(code, session)


if __name__ == "__main__":
    build().launch()
