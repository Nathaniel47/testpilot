"""Score every finished generation outcome of one mode. Resumable, one JSON file per unit.

python -m testpilot.score.batch --mode b0 --split dev
"""

import argparse
import json

from testpilot import config

DATA = config.ROOT / "data"


def outcome_dir(mode: str, seed: int):
    return config.work_dir() / "outcomes" / f"{mode}_s{seed}"


def score_dir(mode: str, seed: int):
    return config.work_dir() / "scores" / f"{mode}_s{seed}"


def main(argv=None) -> int:
    from testpilot.score.metrics import score_unit

    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--flaky", action="store_true", help="also rerun tests 3 times")
    args = ap.parse_args(argv)

    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))["units"]
    repos = {r["name"]: r for r in json.loads((DATA / "repos.json").read_text("utf-8"))["repos"]}
    if args.split != "all":
        units = [u for u in units if u["split"] == args.split]
    src_dir, dst_dir = outcome_dir(args.mode, args.seed), score_dir(args.mode, args.seed)
    dst_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    for unit in units:
        source, target = src_dir / (unit["sha256"] + ".json"), dst_dir / (unit["sha256"] + ".json")
        if target.is_file() or not source.is_file():
            continue
        if args.limit and done >= args.limit:
            break
        outcome = json.loads(source.read_text(encoding="utf-8"))
        entry = repos[unit["repo"]]
        ref = DATA / "reference_tests" / entry["name"]
        row = score_unit(
            DATA / "repos" / entry["name"],
            entry["src"],
            unit,
            outcome["test_code"],
            reference_dir=ref if ref.is_dir() else None,
            check_flaky=args.flaky,
        )
        row |= {"tokens": outcome["tokens"], "calls": outcome["calls"], "repo": unit["repo"]}
        row |= {"n_written": outcome["n_written"], "n_kept": outcome["n_kept"]}
        target.write_text(json.dumps(row), encoding="utf-8")
        done += 1
    print(f"scored {done} units for {args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
