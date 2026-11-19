"""Fetch a repo at a pinned commit, identify its licence, and set its own tests aside."""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

PERMISSIVE = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0"}
TEST_DIR_NAMES = ("tests", "test")


def fetch_repo(url: str, commit: str, dest: Path) -> Path:
    """Shallow-fetch exactly one commit. Nothing from the repo is executed."""
    if (dest / ".git").exists():
        try:
            if _git(dest, "rev-parse", "HEAD").strip() == commit:
                return dest
        except subprocess.CalledProcessError:
            pass
        _rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    _git(dest, "init", "-q")
    _git(dest, "remote", "add", "origin", url)
    for attempt in range(3):
        try:
            _git(dest, "fetch", "-q", "--depth", "1", "origin", commit)
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
    _git(dest, "checkout", "-q", "FETCH_HEAD")
    head = _git(dest, "rev-parse", "HEAD").strip()
    if head != commit:
        raise RuntimeError(f"{url}: expected {commit}, got {head}")
    return dest


def _rmtree(path: Path) -> None:
    def make_writable(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, onerror=make_writable)
        else:
            child.unlink()


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=300
    )
    return out.stdout


def detect_licences(repo: Path) -> set[str]:
    """Identify SPDX ids from LICENSE* files at the repo root, by characteristic phrases."""
    found: set[str] = set()
    for path in sorted(repo.glob("LICEN[CS]E*")):
        if path.is_file():
            found |= licence_ids(path.read_text(encoding="utf-8", errors="replace"))
    return found


def licence_ids(text: str) -> set[str]:
    flat = re.sub(r"\s+", " ", text)
    ids = set()
    if "Apache License" in flat and "Version 2.0" in flat:
        ids.add("Apache-2.0")
    if "Permission is hereby granted, free of charge" in flat:
        ids.add("MIT")
    if "Redistribution and use in source and binary forms" in flat:
        three = any(
            p in flat
            for p in ("Neither the name", "The names of the contributors", "may be used to endorse")
        )
        ids.add("BSD-3-Clause" if three else "BSD-2-Clause")
    return ids


def licence_ok(expected: str, detected: set[str]) -> bool:
    wanted = {part.strip() for part in expected.split(" OR ")}
    return wanted <= detected and wanted <= PERMISSIVE


def separate_tests(repo: Path, reference_dir: Path, src: str = "") -> list[str]:
    """Move the repo's own test folders to reference_dir so generation never sees them.

    Covers top-level tests/ and test/, and test folders nested inside the source package
    (toolz keeps its tests there). Returns the moved paths, relative to the repo root.
    """
    found = [repo / name for name in TEST_DIR_NAMES]
    if src:
        found += [p for p in (repo / src).rglob("*") if p.is_dir() and p.name in TEST_DIR_NAMES]
        earlier = (reference_dir / src).rglob("*") if (reference_dir / src).is_dir() else []
        found += [
            repo / p.relative_to(reference_dir)
            for p in earlier
            if p.is_dir() and p.name in TEST_DIR_NAMES
        ]
    moved = []
    for path in sorted(set(found)):
        rel = path.relative_to(repo)
        target = reference_dir / rel
        if path.is_dir():
            if target.exists():
                _rmtree(target)
                target.rmdir()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            moved.append(rel.as_posix())
        elif target.is_dir():
            moved.append(rel.as_posix())  # already set aside by an earlier run
    return moved
