"""Line and branch coverage of one unit, measured while its tests run in the sandbox."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from testpilot.sandbox.pytest_run import TEST_FILE
from testpilot.sandbox.runner import Sandbox

SCRIPT = """
import json, sys
import coverage, pytest

spec = json.load(open("cov_spec.json"))
cov = coverage.Coverage(branch=True, include=[spec["target"]], data_file="cov.data")
cov.start()
code = pytest.main([spec["tests"], "-q", "-p", "no:cacheprovider"])
cov.stop()
cov.save()
cov.json_report(outfile="cov.json", ignore_errors=True)
print("COVDONE", code)
"""


@dataclass
class UnitCoverage:
    ok: bool = False
    line_total: int = 0
    line_hit: int = 0
    branch_total: int = 0
    branch_hit: int = 0
    missing_lines: list[int] = field(default_factory=list)

    @property
    def line_pct(self) -> float | None:
        return self.line_hit / self.line_total if self.line_total else None

    @property
    def branch_pct(self) -> float | None:
        """None when the unit has no branches (nothing to cover)."""
        return self.branch_hit / self.branch_total if self.branch_total else None


def measure(repo_dir: Path, src: str, unit: dict, test_code: str, timeout=120) -> UnitCoverage:
    target = (Path(src).name / Path(unit["file"]).relative_to(src)).as_posix()
    with Sandbox() as sb:
        sb.copy_tree(repo_dir / src, Path(src).name)
        sb.write(TEST_FILE, test_code)
        sb.write("cov_spec.json", json.dumps({"target": "*/" + target, "tests": TEST_FILE}))
        sb.write("cov_run.py", SCRIPT)
        res = sb.run_script("cov_run.py", timeout=timeout, memory_mb=1024)
        report = sb.code / "cov.json"
        if "COVDONE" not in res.stdout or not report.is_file():
            return UnitCoverage()
        files = json.loads(report.read_text(encoding="utf-8")).get("files", {})
    data = next((v for k, v in files.items() if k.replace("\\", "/").endswith(target)), None)
    return _slice(data, unit["lineno"], unit["end_lineno"]) if data else UnitCoverage()


def _slice(data: dict, first: int, last: int) -> UnitCoverage:
    def inside(n):
        return first <= n <= last

    hit = [n for n in data["executed_lines"] if inside(n)]
    missing = [n for n in data["missing_lines"] if inside(n)]
    ex_br = [b for b in data.get("executed_branches", []) if inside(b[0])]
    mi_br = [b for b in data.get("missing_branches", []) if inside(b[0])]
    return UnitCoverage(
        ok=True,
        line_total=len(hit) + len(missing),
        line_hit=len(hit),
        branch_total=len(ex_br) + len(mi_br),
        branch_hit=len(ex_br),
        missing_lines=sorted(missing),
    )
