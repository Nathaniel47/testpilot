import pytest

from testpilot import __version__
from testpilot.cli import main


def test_main_without_args_succeeds():
    assert main([]) == 0


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
