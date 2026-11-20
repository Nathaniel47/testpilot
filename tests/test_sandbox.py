from testpilot.sandbox.runner import Sandbox


def run_snippet(code: str, **kw):
    with Sandbox() as sb:
        sb.write("job.py", code)
        return sb.run_script("job.py", **kw)


def test_passing_and_failing_pytest():
    with Sandbox() as sb:
        sb.write("test_ok.py", "def test_a():\n    assert 1 + 1 == 2\n")
        assert sb.run_pytest("test_ok.py", "-q", "-p", "no:cacheprovider").ok
        sb.write("test_bad.py", "def test_b():\n    assert 1 == 2\n")
        res = sb.run_pytest("test_bad.py", "-q", "-p", "no:cacheprovider")
        assert not res.ok and "assert 1 == 2" in res.stdout


def test_environment_is_empty_of_secrets(monkeypatch):
    monkeypatch.setenv("TESTPILOT_GROQ_API_KEY", "should-not-leak")
    res = run_snippet("import os\nprint(sorted(os.environ))")
    assert res.ok
    assert "TESTPILOT_GROQ_API_KEY" not in res.stdout and "PATH" not in res.stdout


def test_timeout_kills_infinite_loop():
    res = run_snippet("while True:\n    pass\n", timeout=1)
    assert res.timed_out and not res.ok and res.seconds < 10


def test_memory_limit_kills_allocation():
    res = run_snippet("x = 'x' * 900_000_000\nimport time\ntime.sleep(5)\n", memory_mb=300)
    assert res.memory_exceeded and not res.ok


def test_network_is_blocked():
    code = "import socket\ns = socket.socket()\ns.connect(('127.0.0.1', 9))\n"
    res = run_snippet(code)
    assert not res.ok and "network access is blocked" in res.stderr


def test_write_outside_sandbox_is_blocked(tmp_path):
    target = tmp_path / "escape.txt"
    res = run_snippet(f"open({str(target)!r}, 'w').write('x')\n")
    assert not res.ok and "outside the sandbox" in res.stderr
    assert not target.exists()


def test_write_inside_sandbox_is_allowed():
    res = run_snippet("open('scratch.txt', 'w').write('x')\nprint(open('scratch.txt').read())\n")
    assert res.ok and "x" in res.stdout


def test_sandbox_folder_is_removed():
    with Sandbox() as sb:
        folder = sb.dir
    assert not folder.exists()
