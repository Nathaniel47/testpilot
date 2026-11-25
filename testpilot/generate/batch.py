"""Run one generation mode over many units, resumable: finished units are skipped on rerun.

python -m testpilot.generate.batch --mode b0 --split dev
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from testpilot import config
from testpilot.context.builder import RepoIndex, build_context
from testpilot.generate import guided, modes
from testpilot.llm.budget import EXIT_BUDGET, BudgetExceeded
from testpilot.llm.meta import record_run
from testpilot.subset import take_subset

DATA = config.ROOT / "data"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["b0", "m0", "m1", "m2", "m3"], required=True)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))["units"]
    repos = {r["name"]: r for r in json.loads((DATA / "repos.json").read_text("utf-8"))["repos"]}
    if args.split != "all":
        units = [u for u in units if u["split"] == args.split]
    units = take_subset(units, args.limit)

    out_dir = config.work_dir() / "outcomes" / f"{args.mode}_s{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = None
    if args.mode != "b0":
        from testpilot.llm.client import LLMClient

        client = LLMClient(provider=args.provider, seed=args.seed)
    try:
        return _run_units(args, units, repos, out_dir, client)
    finally:
        # Also on a budget stop or an API error: finished units came from this run.
        if client and (client.stats["calls"] or client.stats["cache_hits"]):
            record_run(client, f"batch-{args.mode}-{args.split}")


def _run_units(args, units, repos, out_dir, client) -> int:
    indexes: dict[str, RepoIndex] = {}
    for unit in units:
        path = out_dir / (unit["sha256"] + ".json")
        if path.is_file():
            continue
        entry = repos[unit["repo"]]
        repo_dir = DATA / "repos" / entry["name"]
        index = indexes.setdefault(entry["name"], RepoIndex(repo_dir, entry["src"]))
        ctx = build_context(unit, index)
        try:
            if args.mode == "b0":
                out = modes.run_b0(ctx, repo_dir, entry["src"])
            elif args.mode in ("m2", "m3"):
                run = guided.run_m2 if args.mode == "m2" else guided.run_m3
                out = run(client, ctx, repo_dir, entry["src"], unit)
            else:
                run = modes.run_m0 if args.mode == "m0" else modes.run_m1
                out = run(client, ctx, repo_dir, entry["src"])
        except BudgetExceeded as exc:
            print(exc)
            return EXIT_BUDGET
        record = {"unit_id": unit["id"], "split": unit["split"], **asdict(out)}
        path.write_text(json.dumps(record), encoding="utf-8")
    summarise(out_dir, units)
    return 0


def summarise(out_dir: Path, units: list[dict]) -> None:
    done = [json.loads((out_dir / (u["sha256"] + ".json")).read_text("utf-8")) for u in units]
    done = [d for d in done if d]
    ok = sum(d["status"] == "ok" for d in done)
    written = sum(d["n_written"] for d in done)
    kept = sum(d["n_kept"] for d in done)
    print(f"{len(done)} units: {ok} with passing tests; {kept}/{written} tests kept")


if __name__ == "__main__":
    raise SystemExit(main())
