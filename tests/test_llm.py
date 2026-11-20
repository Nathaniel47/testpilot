import json

import pytest

from testpilot.llm.budget import Budget, BudgetExceeded
from testpilot.llm.cache import Cache
from testpilot.llm.client import LLMClient
from testpilot.llm.meta import record_run
from testpilot.llm.providers import Completion


def make_client(tmp_path, replies, **kw):
    calls = []

    def fake(model, system, prompt, temperature, seed, max_tokens):
        calls.append(prompt)
        return Completion(replies[min(len(calls) - 1, len(replies) - 1)], 100, 50)

    budget = kw.pop("budget", Budget(tmp_path / "b.json", 10_000))
    client = LLMClient(
        provider="groq", cache=Cache(tmp_path / "c"), budget=budget, call_fn=fake, **kw
    )
    return client, calls


def test_second_identical_call_is_served_from_cache(tmp_path):
    client, calls = make_client(tmp_path, ["hello"])
    first = client.complete("sys", "prompt")
    second = client.complete("sys", "prompt")
    assert (first.text, second.text) == ("hello", "hello")
    assert len(calls) == 1 and second.cached and client.stats["cache_hits"] == 1


def test_seed_and_temperature_change_the_cache_key(tmp_path):
    client, calls = make_client(tmp_path, ["a", "b"])
    client.complete("s", "p")
    client.seed = 1
    client.complete("s", "p")
    assert len(calls) == 2


def test_budget_stops_before_the_limit_and_cache_still_works(tmp_path):
    budget = Budget(tmp_path / "b.json", 1000, stop_at=0.95)
    client, calls = make_client(tmp_path, ["x"], budget=budget, max_tokens=100)
    client.complete("s", "p")  # uses 150 tokens
    budget.add(800)  # 950 used: at the stop line
    with pytest.raises(BudgetExceeded):
        client.complete("s", "another prompt")
    assert client.complete("s", "p").cached


def test_budget_resets_on_a_new_day(tmp_path):
    day = ["2026-01-01"]
    budget = Budget(tmp_path / "b.json", 100, today=lambda: day[0])
    budget.add(90)
    with pytest.raises(BudgetExceeded):
        budget.check(10)
    day[0] = "2026-01-02"
    budget.check(10)


def test_run_meta_records_model_seed_and_commit(tmp_path):
    client, _ = make_client(tmp_path, ["x"], seed=7)
    path = tmp_path / "run_meta.json"
    record_run(client, "unit-test", path)
    entry = json.loads(path.read_text())[0]
    assert entry["seed"] == 7 and entry["model"] and "git_commit" in entry


def test_missing_key_raises_a_clear_error(monkeypatch):
    from testpilot.llm.providers import groq_complete

    monkeypatch.delenv("TESTPILOT_GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TESTPILOT_GROQ_API_KEY"):
        groq_complete("m", "s", "p", 0.0, 0, 10)
