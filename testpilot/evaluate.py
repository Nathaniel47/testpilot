"""One command that runs generation then scoring for several modes and seeds. Resumable.

    python -m testpilot.evaluate --modes b0 m1 m2 m3 --split dev --seeds 0 1 2 --limit 30

Finished units are skipped, so rerunning after the daily token budget stops it (exit code 75)
carries on where it left off. Seeds above 0 are meant for a small subset: --limit picks a seeded
random one spread across libraries (testpilot/subset.py), the same for every mode and seed.
"""

import argparse

from testpilot.generate import batch as generate_batch
from testpilot.llm.budget import EXIT_BUDGET
from testpilot.score import batch as score_batch


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["b0", "m1", "m2", "m3"])
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="N units spread across libraries (seeded, same for every mode and seed)",
    )
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--skip-scoring", action="store_true")
    ap.add_argument("--flag-equivalent", action="store_true", help="slow; see score.batch")
    args = ap.parse_args(argv)

    for seed in args.seeds:
        for mode in args.modes:
            if mode == "b0" and seed > 0:
                continue  # deterministic: seeds change nothing
            gen = ["--mode", mode, "--split", args.split, "--seed", str(seed)]
            gen += ["--provider", args.provider]
            if args.limit:
                gen += ["--limit", str(args.limit)]
            code = generate_batch.main(gen)
            if code == EXIT_BUDGET:
                print("Daily token budget reached; rerun after 00:00 UTC to resume.")
                return EXIT_BUDGET
            if code:
                return code
            if not args.skip_scoring:
                score = ["--mode", mode, "--split", args.split, "--seed", str(seed)]
                if args.flag_equivalent:
                    score.append("--flag-equivalent")
                if args.limit:
                    score += ["--limit", str(args.limit)]
                score_batch.main(score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
