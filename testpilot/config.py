"""Settings come only from TESTPILOT_* environment variables."""

import os
from pathlib import Path

PREFIX = "TESTPILOT_"
ROOT = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(PREFIX + name) or default


def groq_api_key() -> str:
    return env("GROQ_API_KEY")


def gemini_api_key() -> str:
    return env("GEMINI_API_KEY")


def cache_dir() -> Path:
    return Path(env("CACHE_DIR", str(ROOT / "llm_cache")))


def work_dir() -> Path:
    return Path(env("WORK_DIR", str(ROOT / "work")))
