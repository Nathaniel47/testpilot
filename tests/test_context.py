from testpilot.context.builder import RepoIndex, build_context

LIB = '''"""lib"""
from .helpers import clamp


class Box:
    """A box."""

    def __init__(self, size):
        self.size = size

    def grow(self, n):
        """Grow by n."""
        return self._fix(self.size + n)

    def _fix(self, v):
        return clamp(v, 0, 10)


def top(x):
    return Box(x).grow(1)
'''
HELPERS = "def clamp(v, lo, hi):\n    return max(lo, min(hi, v))\n"
USER = "from pkg.lib import top\n\n\ndef use():\n    return top(2)\n"


def make_repo(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "lib.py").write_text(LIB)
    (pkg / "helpers.py").write_text(HELPERS)
    (pkg / "user.py").write_text(USER)
    return RepoIndex(tmp_path, "pkg")


def unit(qualname, file="pkg/lib.py"):
    return {"id": f"x::{qualname}", "file": file, "qualname": qualname, "kind": "function"}


def test_method_context_has_class_helpers_and_module(tmp_path):
    ctx = build_context(unit("Box.grow"), make_repo(tmp_path))
    assert ctx.module == "pkg.lib" and ctx.import_root == "."
    assert ctx.docstring == "Grow by n."
    assert "class Box" in ctx.class_header and "def __init__" in ctx.class_header
    assert [h.label for h in ctx.helpers] == ["Box._fix"]
    assert "from pkg.lib import Box" in ctx.render()


def test_imported_helper_is_resolved(tmp_path):
    ctx = build_context(unit("Box._fix"), make_repo(tmp_path))
    assert [h.label for h in ctx.helpers] == ["pkg.helpers.clamp"]


def test_callers_found_across_files(tmp_path):
    ctx = build_context(unit("top"), make_repo(tmp_path))
    assert ctx.callers and ctx.callers[0].label == "pkg.user.use"


def test_cap_drops_optional_parts_but_never_the_source(tmp_path):
    index = make_repo(tmp_path)
    ctx = build_context(unit("Box.grow"), index, token_cap=1)
    assert "return self._fix" in ctx.source
    assert not ctx.callers and not ctx.helpers and not ctx.class_header
    assert ctx.truncated[-1] == "over_cap"
    assert ctx.truncated.index("helper") < ctx.truncated.index("class_header")


def test_to_dict_is_json_serialisable(tmp_path):
    import json

    ctx = build_context(unit("top"), make_repo(tmp_path))
    assert json.loads(json.dumps(ctx.to_dict()))["unit_id"] == "x::top"
