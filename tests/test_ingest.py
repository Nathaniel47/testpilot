import json
import textwrap

from testpilot import config
from testpilot.ingest.clone import licence_ids, licence_ok, separate_tests
from testpilot.ingest.parse import parse_repo
from testpilot.ingest.sampler import sample_units, split_dev_test

SOURCE = textwrap.dedent(
    '''
    import time


    def good(a, b):
        """Add or compare."""
        if a > b:
            return a - b
        return a + b


    def _hidden(a, b):
        if a > b:
            return a - b
        return a + b


    def clock(a, b):
        if a > b:
            return time.time() - b
        return a + b


    def tiny(a):
        return a


    class Box:
        def size(self, a, b):
            if a > b:
                return a - b
            return a + b

        @property
        def prop(self):
            if self:
                return 1 + 2
            return 3 - 4
    '''
)


def make_repo(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text(SOURCE)
    return tmp_path


def by_name(units):
    return {u.qualname: u for u in units}


def test_parse_marks_eligible_and_reasons(tmp_path):
    units = by_name(parse_repo("r", make_repo(tmp_path), "pkg"))
    assert units["good"].reasons == []
    assert "not_public" in units["_hidden"].reasons
    assert "io_or_nondeterministic" in units["clock"].reasons
    assert "too_short" in units["tiny"].reasons
    assert units["Box.size"].reasons == [] and units["Box.size"].kind == "method"
    assert "property_or_abstract" in units["Box.prop"].reasons


def test_include_private_allows_underscore_names(tmp_path):
    units = by_name(parse_repo("r", make_repo(tmp_path), "pkg", include_private=True))
    assert units["_hidden"].reasons == []


def test_sampling_is_deterministic_and_respects_method_cap(tmp_path):
    units = parse_repo("r", make_repo(tmp_path), "pkg")
    first = sample_units(units, 10, 0, 1, "r")
    assert first == sample_units(units, 10, 0, 1, "r")
    assert [u.qualname for u in first] == ["good"]
    assert {u.qualname for u in sample_units(units, 10, 1, 1, "r")} == {"good", "Box.size"}


def test_split_is_stratified_and_stable():
    class U:
        def __init__(self, i):
            self.id = f"u{i}"

    units = [U(i) for i in range(10)]
    a = split_dev_test(units, 0.3, 7, "r")
    assert a == split_dev_test(units, 0.3, 7, "r")
    assert sum(v == "dev" for v in a.values()) == 3


def test_licence_detection():
    assert licence_ids("Permission is hereby granted, free of charge, to any person") == {"MIT"}
    assert licence_ids("Apache License\nVersion 2.0, January 2004") == {"Apache-2.0"}
    bsd = "Redistribution and use in source and binary forms ... Neither the name of X"
    assert licence_ids(bsd) == {"BSD-3-Clause"}
    assert licence_ok("Apache-2.0 OR BSD-2-Clause", {"Apache-2.0", "BSD-2-Clause"})
    assert not licence_ok("MIT", set())
    assert not licence_ok("GPL-3.0", {"GPL-3.0"})


def test_separate_tests_moves_top_level_and_nested(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_a.py").write_text("x = 1")
    (repo / "pkg" / "tests").mkdir(parents=True)
    (repo / "pkg" / "mod.py").write_text("x = 1")
    ref = tmp_path / "ref"
    moved = separate_tests(repo, ref, "pkg")
    assert sorted(moved) == ["pkg/tests", "tests"]
    assert not (repo / "tests").exists() and (ref / "tests" / "test_a.py").exists()
    assert separate_tests(repo, ref, "pkg") == ["pkg/tests", "tests"]


def test_saved_dataset_is_consistent():
    data = json.loads((config.ROOT / "data" / "units.json").read_text())
    ids = [u["id"] for u in data["units"]]
    assert len(ids) == len(set(ids)) == data["n_units"]
    assert all(not u["reasons"] and u["split"] in {"dev", "test"} for u in data["units"])
    assert not any("/tests/" in u["file"] for u in data["units"])


def test_manifest_is_pinned_and_permissive():
    manifest = json.loads((config.ROOT / "data" / "repos.json").read_text())
    assert 10 <= len(manifest["repos"]) <= 20
    for repo in manifest["repos"]:
        assert len(repo["commit"]) == 40 and set(repo["commit"]) <= set("0123456789abcdef")
        assert licence_ok(repo["licence"], set(repo["licence"].split(" OR ")))
