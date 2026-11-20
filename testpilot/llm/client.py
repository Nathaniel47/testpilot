"""The one door to any LLM: cache first, then budget check, then the provider call."""

from dataclasses import dataclass, field
from pathlib import Path

from testpilot import config
from testpilot.llm.budget import Budget
from testpilot.llm.cache import Cache, cache_key
from testpilot.llm.providers import PROVIDERS, Completion

# Defaults are NOT yet verified against the live APIs; override with TESTPILOT_<PROVIDER>_MODEL.
DEFAULT_MODELS = {"groq": "llama-3.3-70b-versatile", "gemini": "gemini-2.0-flash"}
DAILY_LIMITS = {"groq": 200_000, "gemini": 1_000_000}


@dataclass
class LLMClient:
    provider: str = "groq"
    model: str = ""
    temperature: float = 0.0
    seed: int = 0
    max_tokens: int = 1500
    cache: Cache | None = None
    budget: Budget | None = None
    call_fn: object = None  # injectable for tests
    stats: dict = field(default_factory=lambda: {"calls": 0, "cache_hits": 0, "tokens": 0})

    def __post_init__(self):
        self.model = self.model or config.env(
            f"{self.provider.upper()}_MODEL", DEFAULT_MODELS[self.provider]
        )
        self.cache = self.cache or Cache(config.cache_dir())
        if self.budget is None:
            path = Path(config.work_dir()) / f"budget_{self.provider}.json"
            self.budget = Budget(path, DAILY_LIMITS[self.provider])
        self.call_fn = self.call_fn or PROVIDERS[self.provider]

    def complete(self, system: str, prompt: str) -> Completion:
        key = cache_key(self.provider, self.model, system, prompt, self.temperature, self.seed)
        hit = self.cache.get(key)
        if hit is not None:
            self.stats["cache_hits"] += 1
            return Completion(**{**hit, "cached": True})
        self.budget.check(expected=len(system + prompt) // 4 + self.max_tokens // 2)
        out = self.call_fn(self.model, system, prompt, self.temperature, self.seed, self.max_tokens)
        self.budget.add(out.tokens)
        self.stats["calls"] += 1
        self.stats["tokens"] += out.tokens
        self.cache.put(
            key,
            {
                "text": out.text,
                "prompt_tokens": out.prompt_tokens,
                "completion_tokens": out.completion_tokens,
            },
        )
        return out
