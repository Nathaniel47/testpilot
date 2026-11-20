"""Daily token budget. Free tiers cap tokens per day, so stop before the cap and resume later."""

import json
from datetime import UTC, datetime
from pathlib import Path

EXIT_BUDGET = 75  # EX_TEMPFAIL: try again after 00:00 UTC


class BudgetExceeded(Exception):
    pass


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class Budget:
    def __init__(self, path: Path, daily_limit: int, stop_at: float = 0.95, today=_today):
        self.path = Path(path)
        self.limit = int(daily_limit * stop_at)
        self.today = today

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def used(self) -> int:
        return int(self._load().get(self.today(), 0))

    def check(self, expected: int = 0) -> None:
        if self.used() + expected > self.limit:
            raise BudgetExceeded(
                f"{self.used()} of {self.limit} tokens used today; resume after 00:00 UTC"
            )

    def add(self, tokens: int) -> None:
        data = self._load()
        data[self.today()] = int(data.get(self.today(), 0)) + tokens
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")
