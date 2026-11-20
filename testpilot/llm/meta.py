"""Record what a run used, so numbers can be traced back to a model, seed and commit."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from testpilot import config


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.ROOT, capture_output=True, text=True
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def record_run(client, label: str, path: Path | None = None) -> dict:
    """Append one run's settings to results/run_meta.json (a list of runs)."""
    path = path or config.ROOT / "results" / "run_meta.json"
    entry = {
        "label": label,
        "provider": client.provider,
        "model": client.model,
        "temperature": client.temperature,
        "seed": client.seed,
        "git_commit": git_commit(),
        "time_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "stats": dict(client.stats),
    }
    runs = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    runs.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(runs, indent=1), encoding="utf-8")
    return entry
