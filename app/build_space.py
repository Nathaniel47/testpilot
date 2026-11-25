"""Assemble the folder to upload to the Hugging Face Space: python -m app.build_space"""

import shutil

from testpilot import config

OUT = config.ROOT / "work" / "space_testpilot"


def build_space(out=OUT) -> list[str]:
    shutil.rmtree(out, ignore_errors=True)
    skip = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(config.ROOT / "testpilot", out / "testpilot", ignore=skip)
    (out / "app").mkdir()
    for name in ("__init__.py", "demo_core.py", "gradio_app.py"):
        shutil.copy(config.ROOT / "app" / name, out / "app" / name)
    for name in ("README.md", "app.py", "requirements.txt"):
        shutil.copy(config.ROOT / "app" / "space" / name, out / name)
    return sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())


if __name__ == "__main__":
    files = build_space()
    print(f"{len(files)} files in {OUT}")
