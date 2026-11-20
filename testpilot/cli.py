import argparse
import json
from collections import Counter

from testpilot import __version__, config

DATA = config.ROOT / "data"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testpilot",
        description="Generate unit tests with an LLM and grade them by mutation score.",
    )
    parser.add_argument("--version", action="version", version=f"testpilot {__version__}")
    sub = parser.add_subparsers(dest="command")
    ingest = sub.add_parser(
        "ingest", help="summarise the sampled units, or show one unit's context"
    )
    ingest.add_argument("--context", metavar="UNIT_ID", help="print the LLM context for a unit")
    ingest.add_argument("--token-cap", type=int, default=3000)
    gen = sub.add_parser("generate", help="generate tests for one unit (B0 offline, M0, M1)")
    gen.add_argument("unit_id")
    gen.add_argument("--mode", choices=["b0", "m0", "m1"], default="b0")
    gen.add_argument("--provider", choices=["groq", "gemini"], default="groq")
    gen.add_argument("--seed", type=int, default=0)
    return parser


def cmd_ingest(args: argparse.Namespace) -> int:
    from testpilot.context.builder import RepoIndex, build_context

    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))["units"]
    if not args.context:
        print(f"{len(units)} units from {len({u['repo'] for u in units})} repos")
        by_split = Counter(u["split"] for u in units)
        print(f"dev {by_split['dev']}, test {by_split['test']}")
        for repo, n in sorted(Counter(u["repo"] for u in units).items()):
            print(f"  {repo}: {n}")
        return 0
    unit = next((u for u in units if u["id"] == args.context), None)
    if unit is None:
        print(f"unknown unit id: {args.context}")
        return 2
    manifest = json.loads((DATA / "repos.json").read_text(encoding="utf-8"))
    entry = next(r for r in manifest["repos"] if r["name"] == unit["repo"])
    repo_dir = DATA / "repos" / entry["name"]
    if not repo_dir.is_dir():
        print("repo not downloaded; run: python -m testpilot.ingest.build_dataset")
        return 2
    ctx = build_context(unit, RepoIndex(repo_dir, entry["src"]), args.token_cap)
    print(ctx.render())
    print(f"~{ctx.tokens} tokens; dropped to fit cap: {ctx.truncated or 'nothing'}")
    return 0


def load_unit(unit_id: str):
    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))["units"]
    unit = next((u for u in units if u["id"] == unit_id), None)
    if unit is None:
        return None, None, None
    manifest = json.loads((DATA / "repos.json").read_text(encoding="utf-8"))
    entry = next(r for r in manifest["repos"] if r["name"] == unit["repo"])
    return unit, entry, DATA / "repos" / entry["name"]


def cmd_generate(args: argparse.Namespace) -> int:
    from testpilot.context.builder import RepoIndex, build_context
    from testpilot.generate import modes
    from testpilot.llm.budget import EXIT_BUDGET, BudgetExceeded

    unit, entry, repo_dir = load_unit(args.unit_id)
    if unit is None or not repo_dir.is_dir():
        print("unknown unit id, or repo not downloaded (python -m testpilot.ingest.build_dataset)")
        return 2
    ctx = build_context(unit, RepoIndex(repo_dir, entry["src"]))
    if args.mode == "b0":
        out = modes.run_b0(ctx, repo_dir, entry["src"])
    else:
        from testpilot.llm.client import LLMClient
        from testpilot.llm.meta import record_run

        client = LLMClient(provider=args.provider, seed=args.seed)
        run = modes.run_m0 if args.mode == "m0" else modes.run_m1
        try:
            out = run(client, ctx, repo_dir, entry["src"])
        except BudgetExceeded as exc:
            print(exc)
            return EXIT_BUDGET
        record_run(client, f"generate-{args.mode}")
    print(out.test_code or "# no passing tests")
    print(
        f"# status={out.status} kept={out.n_kept}/{out.n_written} rounds={out.rounds} "
        f"tokens={out.tokens}"
    )
    return 0 if out.test_code else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "generate":
        return cmd_generate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
