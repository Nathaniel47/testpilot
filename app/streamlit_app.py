"""TestPilot demo: paste or pick a Python function; see tests, coverage and mutation score.

Run locally:  streamlit run app/streamlit_app.py
Default mode is the offline template generator, so it needs no key. LLM tests are not offered
here; the cached study results are in results/evaluation.md.
"""

import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.demo_core import EXAMPLES, Refused, analyze  # noqa: E402

MAX_RUNS_PER_SESSION = 8
COOLDOWN_SECONDS = 20

st.set_page_config(page_title="TestPilot demo", page_icon="🧪", layout="wide")
st.title("TestPilot: do the tests catch bugs, or just run the code?")
st.write(
    "Pick an example or paste one Python function. TestPilot writes tests for it, runs them in a "
    "sandbox, then injects small bugs (mutants) and counts how many the tests catch. "
    "Coverage says a line ran; mutation score says a wrong line would be noticed."
)

if "runs" not in st.session_state:
    st.session_state.runs, st.session_state.last = 0, 0.0

choice = st.selectbox("Example", ["(paste your own)", *EXAMPLES])
default = EXAMPLES.get(choice, "")
code = st.text_area("Function to test", value=default, height=260, key=f"code_{choice}")

go = st.button("Generate and score tests", type="primary")
if go:
    wait = COOLDOWN_SECONDS - (time.time() - st.session_state.last)
    if st.session_state.runs >= MAX_RUNS_PER_SESSION:
        st.warning("Demo limit reached for this session. Reload the page to continue.")
    elif wait > 0:
        st.warning(f"Please wait {wait:.0f}s before the next run (this demo is shared).")
    else:
        st.session_state.runs += 1
        st.session_state.last = time.time()
        try:
            with st.spinner("Writing tests, running them, injecting bugs... (about 10 to 40 s)"):
                row = analyze(code)
        except Refused as exc:
            st.error(str(exc))
        else:
            cov, mut = row.get("line_cov"), row.get("mutation_score")
            a, b, c, d = st.columns(4)
            a.metric("Line coverage", "n/a" if cov is None else f"{cov:.0%}")
            b.metric("Mutation score", "n/a" if mut is None else f"{mut:.0%}")
            c.metric("Mutants tried", row.get("n_mutants", 0))
            d.metric("Time", f"{row['seconds']} s")
            if cov is not None and mut is not None and cov - mut > 0.05:
                st.info(
                    f"Gap of {cov - mut:.0%}: these tests run {cov:.0%} of the lines but catch "
                    f"only {mut:.0%} of the injected bugs."
                )
            st.subheader("Generated tests")
            st.code(row.get("test_code") or "# no passing tests were produced", language="python")
            if row.get("survivors"):
                st.subheader("Bugs the tests missed")
                st.table(
                    [
                        {"line": s["line"], "change": s["detail"], "kind": s["operator"]}
                        for s in row["survivors"]
                    ]
                )
                st.caption(
                    "Some of these may be harmless edits that do not change behaviour "
                    "(equivalent mutants), so the score is a lower bound."
                )

st.divider()
st.caption(
    "Offline template generator only, so results are a weak baseline. In the study an LLM with "
    "repair reached about 0.90 mutation score on 61 dev functions versus 0.29 for this baseline "
    "(see results/evaluation.md). Code runs in a locked-down sandbox with time and memory "
    "limits; no data is stored."
)
