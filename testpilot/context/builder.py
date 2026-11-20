"""Function-level context: what an LLM needs to see to write tests for one unit.

Everything here is static (ast only). The unit source is never cut; extra context is added in
order of usefulness and dropped from the end when the token estimate goes over the cap.
"""

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_TOKEN_CAP = 3000
MAX_HELPERS = 3
MAX_CALLERS = 3
SNIPPET_LINES = 25


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


@dataclass
class Snippet:
    label: str
    file: str
    source: str


@dataclass
class Context:
    unit_id: str
    module: str  # dotted import path, e.g. more_itertools.more
    import_root: str  # folder (relative to the repo root) that must be on sys.path
    qualname: str
    kind: str
    signature: str
    docstring: str
    source: str
    class_header: str = ""
    helpers: list[Snippet] = field(default_factory=list)
    callers: list[Snippet] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)

    def render(self) -> str:
        top = self.qualname.split(".")[0]
        parts = [
            f"# Module `{self.module}` (use: `from {self.module} import {top}`)",
            "## Function under test",
            f"```python\n{self.source}\n```",
        ]
        if self.class_header:
            parts += ["## Enclosing class", f"```python\n{self.class_header}\n```"]
        if self.helpers:
            parts.append("## Helpers it uses")
            parts += [f"`{h.label}`\n```python\n{h.source}\n```" for h in self.helpers]
        if self.callers:
            parts.append("## How the library calls it")
            parts += [f"`{c.label}`\n```python\n{c.source}\n```" for c in self.callers]
        return "\n\n".join(parts) + "\n"

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.render())

    def to_dict(self) -> dict:
        return asdict(self)


class RepoIndex:
    """Parsed files of one repo plus a name-to-call-sites map, built once and reused."""

    def __init__(self, repo_dir: Path, src: str):
        self.repo_dir = repo_dir
        self.src = src
        self.root = (repo_dir / src).parent
        self.trees: dict[str, tuple[list[str], ast.Module]] = {}
        self.calls: dict[str, list[tuple[str, str, int]]] = {}
        for path in sorted((repo_dir / src).rglob("*.py")):
            rel = path.relative_to(repo_dir).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            self.trees[rel] = (text.splitlines(), tree)
            for qual, node in iter_functions(tree):
                for call in ast.walk(node):
                    name = _called_name(call)
                    if name:
                        self.calls.setdefault(name, []).append((rel, qual, call.lineno))

    def module_name(self, rel: str) -> str:
        parts = list((self.repo_dir / rel).relative_to(self.root).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)


def iter_functions(tree: ast.Module):
    """Yield (qualname, node) for module-level functions and methods, as parse.py names them."""

    def visit(body, prefix):
        for node in body:
            if isinstance(node, ast.ClassDef):
                yield from visit(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                yield prefix + node.name, node

    yield from visit(tree.body, "")


def _called_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
    return None


def _source(lines: list[str], node, max_lines: int | None = None) -> str:
    first = min([node.lineno] + [d.lineno for d in node.decorator_list])
    chunk = lines[first - 1 : node.end_lineno]
    if max_lines and len(chunk) > max_lines:
        chunk = chunk[:max_lines] + ["    ..."]
    return "\n".join(chunk)


def _signature(node) -> str:
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"def {node.name}({ast.unparse(node.args)}){ret}"


def build_context(unit: dict, index: RepoIndex, token_cap: int = DEFAULT_TOKEN_CAP) -> Context:
    lines, tree = index.trees[unit["file"]]
    funcs = dict(iter_functions(tree))
    node = funcs[unit["qualname"]]
    ctx = Context(
        unit_id=unit["id"],
        module=index.module_name(unit["file"]),
        import_root=index.root.relative_to(index.repo_dir).as_posix() or ".",
        qualname=unit["qualname"],
        kind=unit["kind"],
        signature=_signature(node),
        docstring=ast.get_docstring(node) or "",
        source=_source(lines, node),
    )
    if "." in unit["qualname"]:
        ctx.class_header = _class_header(tree, lines, unit["qualname"].rsplit(".", 1)[0])
    ctx.helpers = _helpers(unit, node, funcs, lines, tree, index)
    ctx.callers = _callers(unit, index)
    _fit(ctx, token_cap)
    return ctx


def _class_header(tree: ast.Module, lines: list[str], class_path: str) -> str:
    body = tree.body
    cls = None
    for name in class_path.split("."):
        cls = next((n for n in body if isinstance(n, ast.ClassDef) and n.name == name), None)
        if cls is None:
            return ""
        body = cls.body
    out = [f"class {cls.name}({', '.join(ast.unparse(b) for b in cls.bases)}):"]
    doc = ast.get_docstring(cls)
    if doc:
        out.append(f'    """{doc.splitlines()[0]}"""')
    init = next(
        (n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None
    )
    if init:
        out.append(_source(lines, init, SNIPPET_LINES))
    return "\n".join(out)


def _helpers(unit, node, funcs, lines, tree, index) -> list[Snippet]:
    wanted: list[str] = []
    for call in ast.walk(node):
        name = _called_name(call)
        if name and name not in wanted and name != node.name:
            wanted.append(name)
    class_path = unit["qualname"].rsplit(".", 1)[0] + "." if "." in unit["qualname"] else ""
    found: list[Snippet] = []
    imported = _repo_imports(tree, unit["file"], index)
    for name in wanted:
        if len(found) == MAX_HELPERS:
            break
        if class_path + name in funcs:
            found.append(
                Snippet(
                    f"{class_path}{name}",
                    unit["file"],
                    _source(lines, funcs[class_path + name], SNIPPET_LINES),
                )
            )
        elif name in funcs:
            found.append(Snippet(name, unit["file"], _source(lines, funcs[name], SNIPPET_LINES)))
        elif name in imported:
            rel = imported[name]
            other_lines, other_tree = index.trees[rel]
            target = dict(iter_functions(other_tree)).get(name)
            if target is not None:
                found.append(
                    Snippet(
                        f"{index.module_name(rel)}.{name}",
                        rel,
                        _source(other_lines, target, SNIPPET_LINES),
                    )
                )
    return found


def _repo_imports(tree: ast.Module, rel: str, index: RepoIndex) -> dict[str, str]:
    """Map imported names to the repo file that defines them (relative and absolute imports)."""
    base = Path(rel).parent
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            folder = base
            for _ in range(node.level - 1):
                folder = folder.parent
            candidates = [folder / (node.module.replace(".", "/") + ".py")]
        else:
            candidates = [
                Path(index.root.relative_to(index.repo_dir))
                / (node.module.replace(".", "/") + ".py")
            ]
        for cand in candidates:
            if cand.as_posix() in index.trees:
                for alias in node.names:
                    out[alias.asname or alias.name] = cand.as_posix()
    return out


def _callers(unit: dict, index: RepoIndex) -> list[Snippet]:
    name = unit["qualname"].rsplit(".", 1)[-1]
    if name.startswith("__"):
        return []
    seen, out = set(), []
    for rel, qual, _line in sorted(index.calls.get(name, [])):
        if (rel, qual) == (unit["file"], unit["qualname"]) or (rel, qual) in seen:
            continue
        seen.add((rel, qual))
        lines, tree = index.trees[rel]
        node = dict(iter_functions(tree)).get(qual)
        if node is not None:
            out.append(Snippet(f"{index.module_name(rel)}.{qual}", rel, _source(lines, node, 15)))
        if len(out) == MAX_CALLERS:
            break
    return out


def _fit(ctx: Context, cap: int) -> None:
    """Drop optional context from the least useful end until the estimate fits the cap."""
    while ctx.tokens > cap:
        if ctx.callers:
            ctx.callers.pop()
            ctx.truncated.append("caller")
        elif ctx.helpers:
            ctx.helpers.pop()
            ctx.truncated.append("helper")
        elif ctx.class_header:
            ctx.class_header = ""
            ctx.truncated.append("class_header")
        else:
            ctx.truncated.append("over_cap")
            break
