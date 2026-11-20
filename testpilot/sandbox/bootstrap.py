"""Runs inside the sandbox process. Installs soft guards, then runs the requested job.

Usage: python bootstrap.py <sandbox_dir> pytest <pytest args...>
       python bootstrap.py <sandbox_dir> script <path.py>

The guards stop accidents (a test that opens a socket or writes outside its folder). They are
not a security boundary: Docker (see Dockerfile and CI) is the real second layer.
"""

import builtins
import os
import runpy
import socket
import sys


def install_guards(sandbox: str) -> None:
    root = os.path.realpath(sandbox)

    def blocked(*_a, **_k):
        raise PermissionError("network access is blocked in the TestPilot sandbox")

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    socket.getaddrinfo = blocked

    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if isinstance(file, str | bytes | os.PathLike) and any(c in mode for c in "wax+"):
            name = os.fsdecode(file)
            path = os.path.realpath(name)
            try:
                inside = os.path.commonpath([path, root]) == root
            except ValueError:  # other drive, or a device path
                inside = False
            if not inside and os.path.normcase(path) != os.path.normcase(
                os.path.realpath(os.devnull)
            ):
                raise PermissionError(f"write outside the sandbox folder: {path}")
        return real_open(file, mode, *args, **kwargs)

    builtins.open = guarded_open
    os.system = lambda *_a, **_k: blocked()


def main() -> int:
    sandbox, mode, *rest = sys.argv[1:]
    sys.path.insert(0, os.path.join(sandbox, "code"))
    sys.path.extend(d for d in os.environ.get("TESTPILOT_SANDBOX_SITE", "").split(os.pathsep) if d)
    install_guards(sandbox)
    os.chdir(os.path.join(sandbox, "code"))
    if mode == "pytest":
        import pytest

        return int(pytest.main(rest))
    sys.argv = rest
    runpy.run_path(rest[0], run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
