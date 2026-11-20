"""Find out which candidate units can really be imported and looked up, inside the sandbox.

This is the first time repo code runs (module import only). A unit whose module cannot be
imported, or whose name does not resolve to a callable, gets a reason and is never sampled.
"""

import json
from pathlib import Path

from testpilot.context.builder import RepoIndex
from testpilot.ingest.parse import Unit
from testpilot.sandbox.runner import Sandbox

PROBE = """
import importlib, json

spec = json.load(open("probe_input.json"))
out = {}
for mod, quals in spec.items():
    try:
        module = importlib.import_module(mod)
    except BaseException as exc:
        out[mod] = {"__error__": f"{type(exc).__name__}: {exc}"[:200]}
        continue
    res = {}
    for qual in quals:
        obj = module
        try:
            for part in qual.split("."):
                obj = getattr(obj, part)
            res[qual] = "" if callable(obj) else "not_callable"
        except BaseException as exc:
            res[qual] = type(exc).__name__
    out[mod] = res
print("PROBE" + json.dumps(out))
"""


def probe_units(repo_dir: Path, src: str, index: RepoIndex, units: list[Unit]) -> dict[str, str]:
    """Return {unit_id: problem} for units that fail; units that pass are absent."""
    spec: dict[str, list[str]] = {}
    by_module: dict[str, list[Unit]] = {}
    for unit in units:
        module = index.module_name(unit.file)
        spec.setdefault(module, []).append(unit.qualname)
        by_module.setdefault(module, []).append(unit)
    with Sandbox() as sb:
        sb.copy_tree(repo_dir / src, Path(src).name)
        sb.write("probe_input.json", json.dumps(spec))
        sb.write("probe.py", PROBE)
        result = sb.run_script("probe.py", timeout=180, memory_mb=1024)
    line = next((x for x in reversed(result.stdout.splitlines()) if x.startswith("PROBE")), None)
    if line is None:
        detail = "timeout" if result.timed_out else result.stderr.strip().splitlines()[-1:]
        return {u.id: f"probe_crashed: {detail}" for u in units}
    found = json.loads(line[len("PROBE") :])
    problems: dict[str, str] = {}
    for module, members in by_module.items():
        res = found.get(module, {})
        for unit in members:
            if "__error__" in res:
                problems[unit.id] = "module_not_importable"
            elif res.get(unit.qualname, "missing"):
                problems[unit.id] = "name_not_resolved"
    return problems
