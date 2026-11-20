"""The only place generated tests and target code run.

Each run gets a throwaway folder with a copy of the code, an empty environment, a wall-clock
limit and a memory watchdog over the whole process tree. Network and out-of-folder writes are
blocked by soft guards (bootstrap.py); Docker is the hard boundary in CI and the demo.
"""

import os
import shutil
import site
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

BOOTSTRAP = Path(__file__).with_name("bootstrap.py")
MAX_OUTPUT = 20_000


@dataclass
class RunResult:
    returncode: int | None
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False
    memory_exceeded: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.memory_exceeded


def clean_env(sandbox: Path) -> dict[str, str]:
    env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "HOME": str(sandbox),
        "TMPDIR": str(sandbox),
        "TEMP": str(sandbox),
        "TMP": str(sandbox),
    }
    site_dirs = [*site.getsitepackages(), site.getusersitepackages()]
    env["TESTPILOT_SANDBOX_SITE"] = os.pathsep.join(d for d in site_dirs if os.path.isdir(d))
    if sys.platform == "win32":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return env


class Sandbox:
    """A temporary folder: `code/` holds copied source and test files, the rest is scratch."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="testpilot_"))
        self.code = self.dir / "code"
        self.code.mkdir()

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *_exc) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def copy_tree(self, src: Path, dest_rel: str = "") -> None:
        shutil.copytree(
            src,
            self.code / dest_rel,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    def write(self, rel: str, text: str) -> Path:
        path = self.code / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_pytest(self, *args: str, timeout: float = 30, memory_mb: int = 512) -> RunResult:
        return self._run(["pytest", *args], timeout, memory_mb)

    def run_script(self, rel: str, timeout: float = 30, memory_mb: int = 512) -> RunResult:
        return self._run(["script", str(self.code / rel)], timeout, memory_mb)

    def _run(self, job: list[str], timeout: float, memory_mb: int) -> RunResult:
        boot = self.dir / "bootstrap.py"
        shutil.copy(BOOTSTRAP, boot)
        cmd = [sys.executable, str(boot), str(self.dir), *job]
        start = time.monotonic()
        out_path, err_path = self.dir / "stdout.txt", self.dir / "stderr.txt"
        with open(out_path, "wb") as out, open(err_path, "wb") as err:
            proc = subprocess.Popen(
                cmd, cwd=self.dir, env=clean_env(self.dir), stdout=out, stderr=err,
                stdin=subprocess.DEVNULL,
            )  # fmt: skip
            timed_out = memory_exceeded = False
            while proc.poll() is None:
                if time.monotonic() - start > timeout:
                    timed_out = True
                elif _tree_rss_mb(proc.pid) > memory_mb:
                    memory_exceeded = True
                if timed_out or memory_exceeded:
                    _kill_tree(proc.pid)
                    proc.wait()
                    break
                time.sleep(0.02)
        return RunResult(
            returncode=proc.returncode,
            stdout=_read(out_path),
            stderr=_read(err_path),
            seconds=time.monotonic() - start,
            timed_out=timed_out,
            memory_exceeded=memory_exceeded,
        )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[-MAX_OUTPUT:]


def _tree_rss_mb(pid: int) -> float:
    try:
        procs = [psutil.Process(pid), *psutil.Process(pid).children(recursive=True)]
        return sum(p.memory_info().rss for p in procs if p.is_running()) / 1e6
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0


def _kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass
