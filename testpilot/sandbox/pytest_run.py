"""Run one generated test file against a repo's source inside the sandbox."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from testpilot.sandbox.runner import Sandbox

TEST_FILE = "test_generated.py"
MEMORY_ADDRESS = re.compile(r"\b0x[0-9A-Fa-f]{6,}\b")
SANDBOX_PATH = re.compile(r"[^\s'\"]*testpilot_[A-Za-z0-9_]{6,}")


@dataclass
class TestRun:
    __test__ = False  # not a pytest class

    passed: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # test name -> failure message
    error: str = ""  # collection error, crash or timeout: nothing could be judged
    seconds: float = 0.0

    @property
    def all_passed(self) -> bool:
        return not self.error and not self.failed and bool(self.passed)

    def failure_text(self, limit: int = 2500) -> str:
        """Failure details without what changes between runs (temp folder, memory addresses).

        These end up in repair prompts; a prompt that differs every run never hits the cache.
        """
        if self.error:
            text = self.error[-limit:]
        else:
            text = "\n\n".join(f"{n}: {m}" for n, m in self.failed.items())[:limit]
        return MEMORY_ADDRESS.sub("0x...", SANDBOX_PATH.sub("<sandbox>", text))


def run_tests(repo_dir: Path, src: str, test_code: str, timeout: float = 60) -> TestRun:
    with Sandbox() as sb:
        sb.copy_tree(repo_dir / src, Path(src).name)
        sb.write(TEST_FILE, test_code)
        res = sb.run_pytest(
            TEST_FILE, "-q", "--tb=short", "-p", "no:cacheprovider", "--junitxml=junit.xml",
            timeout=timeout,
        )  # fmt: skip
        report = sb.code / "junit.xml"
        if res.timed_out or res.memory_exceeded or not report.is_file():
            why = (
                "timed out" if res.timed_out else "memory limit hit" if res.memory_exceeded else ""
            )
            return TestRun(error=why or (res.stdout + res.stderr)[-2500:], seconds=res.seconds)
        return _parse_junit(report, res.seconds)


def _parse_junit(path: Path, seconds: float) -> TestRun:
    run = TestRun(seconds=seconds)
    for case in ET.parse(path).getroot().iter("testcase"):
        name = case.get("name", "?")
        bad = case.find("failure") if case.find("failure") is not None else case.find("error")
        if bad is None:
            if case.find("skipped") is None:
                run.passed.append(name)
        elif name == "test_generated" or case.get("classname", "") == "":
            run.error = (bad.get("message") or "") + "\n" + (bad.text or "")
        else:
            run.failed[name] = ((bad.get("message") or "") + "\n" + (bad.text or ""))[-800:]
    return run
