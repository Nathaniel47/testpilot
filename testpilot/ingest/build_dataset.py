"""Rebuild the dataset: python -m testpilot.ingest.build_dataset

Fetches the pinned repos, checks licences, moves their tests aside, inventories every function,
samples units with a fixed seed, saves the dev/test split and writes results/data_report.md.
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from testpilot import config
from testpilot.context.builder import RepoIndex, build_context
from testpilot.ingest.clone import detect_licences, fetch_repo, licence_ok, separate_tests
from testpilot.ingest.parse import Unit, parse_repo
from testpilot.ingest.runnable import probe_units
from testpilot.ingest.sampler import sample_units, split_dev_test

DATA = config.ROOT / "data"
RESULTS = config.ROOT / "results"


def load_manifest() -> dict:
    return json.loads((DATA / "repos.json").read_text(encoding="utf-8"))


def count_lines(repo_dir: Path, src: str) -> int:
    total = 0
    for path in (repo_dir / src).rglob("*.py"):
        total += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return total


def process_repo(entry: dict, manifest: dict, repos_dir: Path, ref_dir: Path) -> dict:
    repo_dir = fetch_repo(entry["url"], entry["commit"], repos_dir / entry["name"])
    detected = detect_licences(repo_dir)
    if not licence_ok(entry["licence"], detected):
        raise SystemExit(f"Licence check failed for {entry['name']}: {sorted(detected)}")
    moved = separate_tests(repo_dir, ref_dir / entry["name"], entry["src"])
    units = parse_repo(entry["name"], repo_dir, entry["src"], entry.get("include_private", False))
    index = RepoIndex(repo_dir, entry["src"])
    candidates = [u for u in units if not u.reasons]
    for unit_id, problem in probe_units(repo_dir, entry["src"], index, candidates).items():
        next(u for u in units if u.id == unit_id).reasons.append(problem)
    picked = sample_units(
        units,
        manifest["units_per_repo"],
        manifest["max_methods_per_repo"],
        manifest["seed"],
        entry["name"],
    )
    split = split_dev_test(picked, manifest["dev_fraction"], manifest["seed"], entry["name"])
    unit_rows = {u.id: u.to_dict() for u in picked}
    contexts = {uid: build_context(row, index) for uid, row in unit_rows.items()}
    return {
        "contexts": contexts,
        "entry": entry,
        "detected_licences": sorted(detected),
        "licence_ok": licence_ok(entry["licence"], detected),
        "tests_moved": moved,
        "src_lines": count_lines(repo_dir, entry["src"]),
        "units": units,
        "picked": picked,
        "split": split,
    }


def build(repos_dir: Path | None = None, ref_dir: Path | None = None) -> list[dict]:
    manifest = load_manifest()
    repos_dir = repos_dir or DATA / "repos"
    ref_dir = ref_dir or DATA / "reference_tests"
    results = [process_repo(e, manifest, repos_dir, ref_dir) for e in manifest["repos"]]
    bad = [r["entry"]["name"] for r in results if not r["licence_ok"]]
    if bad:
        raise SystemExit(f"Licence check failed for: {bad}")
    validate(results)
    save(results, manifest)
    return results


def validate(results: list[dict]) -> None:
    ids = [u.id for r in results for u in r["picked"]]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate unit ids")
    for r in results:
        if not r["picked"]:
            raise SystemExit(f"no eligible units in {r['entry']['name']}")
        if any(u.reasons for u in r["picked"]):
            raise SystemExit("ineligible unit was sampled")


def save(results: list[dict], manifest: dict) -> None:
    rows = []
    for r in results:
        for u in r["picked"]:
            row = u.to_dict()
            row["split"] = r["split"][u.id]
            row["context_tokens"] = r["contexts"][u.id].tokens
            rows.append(row)
    out = {
        "seed": manifest["seed"],
        "n_units": len(rows),
        "units": rows,
    }
    reserve = {
        r["entry"]["name"]: [
            u.id
            for u in sample_units(
                [u for u in r["units"] if u.id not in {p.id for p in r["picked"]}],
                10**6,
                10**6,
                manifest["seed"],
                r["entry"]["name"] + ":reserve",
            )
        ]
        for r in results
    }
    (DATA / "reserve.json").write_text(json.dumps(reserve, indent=1) + "\n", encoding="utf-8")
    (DATA / "units.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    facts = {
        r["entry"]["name"]: {
            "commit": r["entry"]["commit"],
            "licence_expected": r["entry"]["licence"],
            "licence_detected": r["detected_licences"],
            "src_lines": r["src_lines"],
            "tests_moved": r["tests_moved"],
            "functions_total": len(r["units"]),
            "eligible": sum(1 for u in r["units"] if not u.reasons),
            "sampled": len(r["picked"]),
        }
        for r in results
    }
    (DATA / "repo_facts.json").write_text(json.dumps(facts, indent=1) + "\n", encoding="utf-8")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "data_report.md").write_text(render_report(results, manifest), encoding="utf-8")


def render_report(results: list[dict], manifest: dict) -> str:
    picked = [u for r in results for u in r["picked"]]
    splits = Counter(r["split"][u.id] for r in results for u in r["picked"])
    kinds = Counter(u.kind for u in picked)
    reasons = Counter(x for r in results for u in r["units"] for x in u.reasons)
    total_units = sum(len(r["units"]) for r in results)
    eligible = sum(1 for r in results for u in r["units"] if not u.reasons)
    ctxs = [r["contexts"][u.id] for r in results for u in r["picked"]]
    tokens = [c.tokens for c in ctxs]
    locs = [u.loc for u in picked]
    sites = [u.mutable_sites for u in picked]
    lines = [
        "# Data report",
        "",
        f"Seed {manifest['seed']}. Built by `python -m testpilot.ingest.build_dataset`. "
        "Repo code runs only inside the sandbox, and only to import modules (the runnable check).",
        "",
        "## Totals",
        "",
        f"- Repos: {len(results)}, source lines: {sum(r['src_lines'] for r in results):,}",
        f"- Functions and methods found: {total_units:,}; eligible after static filters: "
        f"{eligible:,} ({eligible / total_units:.0%})",
        f"- Sampled units: {len(picked)} (dev {splits['dev']}, test {splits['test']})",
        "- Kinds: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())),
        f"- Unit length (lines): median {statistics.median(locs)}, "
        f"min {min(locs)}, max {max(locs)}",
        f"- Mutation-site count per unit: median {statistics.median(sites)}, "
        f"min {min(sites)}, max {max(sites)}",
        f"- With docstring: {sum(u.has_docstring for u in picked) / len(picked):.0%}",
        f"- Context size (estimated tokens): median {statistics.median(tokens)}, "
        f"max {max(tokens)}; units where optional context was dropped to fit the cap: "
        f"{sum(bool(c.truncated) for c in ctxs)}; with helpers: "
        f"{sum(bool(c.helpers) for c in ctxs)}; with callers: {sum(bool(c.callers) for c in ctxs)}",
        "",
        "## Per repo",
        "",
        "| Repo | Licence (detected) | Src lines | Functions | Eligible | Sampled | Dev | Test |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        s = Counter(r["split"].values())
        lines.append(
            f"| {r['entry']['name']} | {' + '.join(r['detected_licences'])} | {r['src_lines']:,} "
            f"| {len(r['units'])} | {sum(1 for u in r['units'] if not u.reasons)} "
            f"| {len(r['picked'])} | {s['dev']} | {s['test']} |"
        )
    lines += ["", "## Why functions were filtered out", "",
              "A function can have several reasons, so counts add up to more than the total.", "",
              "| Reason | Functions |", "|---|---:|"]  # fmt: skip
    lines += [f"| {k} | {v:,} |" for k, v in reasons.most_common()]
    lines += ["", "## Sample records", ""]
    for u in picked[:: max(1, len(picked) // 4)][:4]:
        lines.append(
            f"- `{u.id}` ({u.kind}, lines {u.lineno}-{u.end_lineno}, {u.branches} branches, "
            f"{u.mutable_sites} mutation sites, split {_split_of(results, u)})"
        )
    lines += ["", "## Quality problems found", ""]
    lines += quality_problems(results, manifest)
    return "\n".join(lines) + "\n"


def _split_of(results: list[dict], unit: Unit) -> str:
    for r in results:
        if unit.id in r["split"]:
            return r["split"][unit.id]
    return "?"


def quality_problems(results: list[dict], manifest: dict) -> list[str]:
    want = manifest["units_per_repo"]
    out = []
    short = [
        f"{r['entry']['name']} ({len(r['picked'])})" for r in results if len(r["picked"]) < want
    ]
    if short:
        out.append(f"- Fewer than {want} eligible units: " + ", ".join(short) + ".")
    for r in results:
        n_methods = sum(u.kind != "function" for u in r["picked"])
        if n_methods == len(r["picked"]):
            out.append(f"- {r['entry']['name']}: every sampled unit is a method.")
        if not r["tests_moved"]:
            out.append(f"- {r['entry']['name']}: no tests/ or test/ folder found to set aside.")
    out += [
        "- Eligibility is decided statically. A unit can still fail to run alone (needs a "
        "constructed object, a fixture, or a helper); Step 4's sandbox run measures this and "
        "units that cannot be run are replaced from `data/reserve.json` (the other eligible "
        "units, in seeded order).",
        "- Banned-name filtering is by name, so it is conservative: a function that uses a local "
        "variable called `time` is dropped, and an indirect call to a clock is not caught.",
        "- Popular libraries may be in the LLM's training data, which can inflate scores. Step 6 "
        "measures how often generated tests reproduce the removed reference tests.",
    ]
    return out


if __name__ == "__main__":
    build()
