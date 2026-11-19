"""Static function inventory of a source tree. Parses with ast; never imports or runs code."""

import ast
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_MODULES = {"__main__", "compat", "_compat"}
BANNED_NAMES = {
    "open", "input", "exec", "eval", "compile", "socket", "subprocess", "system", "popen",
    "random", "time", "sleep", "now", "today", "urlopen", "environ", "getenv", "thread",
    "Thread", "uuid4", "getpass", "sys", "stdin", "stdout", "stderr",
}  # fmt: skip
MUTABLE_NODES = (ast.BinOp, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.IfExp, ast.Return)


@dataclass
class Unit:
    repo: str
    id: str
    file: str
    qualname: str
    kind: str  # function | method | classmethod | staticmethod
    lineno: int
    end_lineno: int
    loc: int
    n_args: int
    has_docstring: bool
    branches: int
    mutable_sites: int
    sha256: str
    reasons: list[str]  # why it is NOT eligible; empty means eligible

    def to_dict(self) -> dict:
        return asdict(self)


def parse_repo(
    repo_name: str, repo_dir: Path, src: str, include_private: bool = False
) -> list[Unit]:
    units: list[Unit] = []
    for path in sorted((repo_dir / src).rglob("*.py")):
        rel = path.relative_to(repo_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        units.extend(_collect(repo_name, rel, path.stem, text, tree, include_private))
    return units


def _collect(
    repo: str, rel: str, stem: str, text: str, tree: ast.Module, include_private: bool
) -> list[Unit]:
    lines = text.splitlines()
    out: list[Unit] = []

    def ok(name: str) -> bool:
        return _public(name) or (include_private and not name.startswith("__"))

    def visit(body: list[ast.stmt], prefix: str, in_class: bool, public_scope: bool):
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.", True, public_scope and ok(node.name))
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                out.append(
                    _unit(
                        repo,
                        rel,
                        stem,
                        lines,
                        node,
                        prefix,
                        in_class,
                        public_scope and ok(node.name),
                    )
                )

    visit(tree.body, "", False, True)
    return out


def _public(name: str) -> bool:
    return not name.startswith("_")


def _kind(node, in_class: bool) -> str:
    decos = {d.id for d in node.decorator_list if isinstance(d, ast.Name)}
    if not in_class:
        return "function"
    if "staticmethod" in decos:
        return "staticmethod"
    if "classmethod" in decos:
        return "classmethod"
    return "method"


def _unit(repo, rel, stem, lines, node, prefix, in_class, public_scope) -> Unit:
    qual = prefix + node.name
    segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
    nodes = list(ast.walk(node))
    names = {n.id for n in nodes if isinstance(n, ast.Name)}
    names |= {n.attr for n in nodes if isinstance(n, ast.Attribute)}
    names |= {a.name.split(".")[0] for n in nodes if isinstance(n, ast.Import) for a in n.names}
    decos = {ast.unparse(d) for d in node.decorator_list}
    branches = sum(
        isinstance(n, ast.If | ast.For | ast.While | ast.BoolOp | ast.IfExp) for n in nodes
    )
    returns = any(isinstance(n, ast.Return | ast.Yield | ast.YieldFrom) for n in nodes)
    loc = node.end_lineno - node.lineno + 1
    sites = sum(isinstance(n, MUTABLE_NODES) for n in nodes)
    reasons = []
    if stem in SKIP_MODULES:
        reasons.append("skipped_module")
    if not public_scope:
        reasons.append("not_public")
    if isinstance(node, ast.AsyncFunctionDef):
        reasons.append("async")
    if any("property" in d or "setter" in d or "abstract" in d for d in decos):
        reasons.append("property_or_abstract")
    if any(isinstance(n, ast.FunctionDef) and n is not node for n in nodes):
        reasons.append("nested_function")
    if names & BANNED_NAMES:
        reasons.append("io_or_nondeterministic")
    if not returns:
        reasons.append("no_return_value")
    if loc < 4:
        reasons.append("too_short")
    if loc > 60:
        reasons.append("too_long")
    if sites < 2:
        reasons.append("few_mutation_sites")
    if any(isinstance(n, ast.Raise) and "NotImplementedError" in ast.dump(n) for n in nodes):
        reasons.append("not_implemented")
    a = node.args
    return Unit(
        repo=repo,
        id=f"{repo}:{rel}:{qual}",
        file=rel,
        qualname=qual,
        kind=_kind(node, in_class),
        lineno=node.lineno,
        end_lineno=node.end_lineno,
        loc=loc,
        n_args=len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs),
        has_docstring=ast.get_docstring(node) is not None,
        branches=branches,
        mutable_sites=sites,
        sha256=hashlib.sha256(segment.encode()).hexdigest()[:16],
        reasons=reasons,
    )
