"""Test-and-score the changed functions of a repo; the engine behind the GitHub Action.

Offline mode (b0) needs no API key. LLM modes (m1, m3) use the cached client.
"""

import subprocess
from pathlib import Path

from testpilot.context.builder import RepoIndex, build_context
from testpilot.generate import guided, modes
from testpilot.ingest.parse import parse_repo
from testpilot.score.metrics import score_unit

MODES = ("b0", "m1", "m3")


def changed_python_files(repo_dir: Path, base_ref: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", f"{base_ref}...HEAD"],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    )  # fmt: skip
    return [f for f in out.stdout.splitlines() if f.endswith(".py")]


def eligible_units(repo_dir: Path, src: str, files: list[str]) -> list[dict]:
    wanted = {Path(f).as_posix() for f in files}
    units = parse_repo(repo_dir.name, repo_dir, src)
    return [u.to_dict() for u in units if u.file in wanted and not u.reasons]


def check(
    repo_dir: Path,
    src: str,
    files: list[str],
    mode: str = "b0",
    max_units: int = 5,
    seed: int = 0,
    client=None,
) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode != "b0" and client is None:
        from testpilot.llm.client import LLMClient

        client = LLMClient(seed=seed)
    units = eligible_units(repo_dir, src, files)[:max_units]
    index = RepoIndex(repo_dir, src)
    rows = []
    for unit in units:
        ctx = build_context(unit, index)
        if mode == "b0":
            out = modes.run_b0(ctx, repo_dir, src)
        elif mode == "m1":
            out = modes.run_m1(client, ctx, repo_dir, src)
        else:
            out = guided.run_m3(client, ctx, repo_dir, src, unit)
        row = score_unit(repo_dir, src, unit, out.test_code, seed=seed)
        rows.append(
            row
            | {
                "qualname": unit["qualname"],
                "file": unit["file"],
                "tokens": out.tokens,
                "test_code": out.test_code,
            }
        )
    return rows


def _pct(v) -> str:
    return "n/a" if v is None else f"{v:.0%}"


def summary_markdown(rows: list[dict], mode: str, n_candidates: int | None = None) -> str:
    if not rows:
        return "## TestPilot\n\nNo eligible changed functions found.\n"
    lines = [
        "## TestPilot: mutation score of generated tests",
        "",
        f"Mode `{mode}`. Mutation score = share of injected bugs the tests catch; line coverage "
        "is shown beside it because tests can run code without checking it.",
        "",
        "| Function | Tests | Line cov | Mutation score | Mutants | Surviving bugs |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        surv = "; ".join(f"line {s['line']}: {s['detail']}" for s in r.get("survivors", [])[:3])
        lines.append(
            f"| `{r['file']}::{r['qualname']}` | {'yes' if r['has_tests'] else 'none passed'} "
            f"| {_pct(r.get('line_cov'))} | {_pct(r.get('mutation_score'))} "
            f"| {r.get('n_mutants', 0)} | {surv or '-'} |"
        )
    scored = [r["mutation_score"] for r in rows if r.get("mutation_score") is not None]
    if scored:
        mean = sum(scored) / len(scored)
        lines += [
            "",
            f"**Mean mutation score: {mean:.0%}** over {len(scored)} function(s). "
            "Some surviving mutants may be equivalent (same behaviour).",
        ]
    return "\n".join(lines) + "\n"
