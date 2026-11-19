from testpilot import config


def test_env_reads_prefixed_variable(monkeypatch):
    monkeypatch.setenv("TESTPILOT_GROQ_API_KEY", "abc")
    assert config.groq_api_key() == "abc"


def test_env_ignores_unprefixed_variable(monkeypatch):
    monkeypatch.delenv("TESTPILOT_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "leak")
    assert config.gemini_api_key() == ""


def test_dirs_default_and_override(monkeypatch, tmp_path):
    monkeypatch.delenv("TESTPILOT_CACHE_DIR", raising=False)
    assert config.cache_dir() == config.ROOT / "llm_cache"
    monkeypatch.setenv("TESTPILOT_WORK_DIR", str(tmp_path))
    assert config.work_dir() == tmp_path


def test_env_example_has_only_prefixed_empty_names():
    lines = [
        line
        for line in (config.ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert lines
    for line in lines:
        name, _, value = line.partition("=")
        assert name.startswith("TESTPILOT_") and value == ""
