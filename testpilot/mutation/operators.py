"""Mutation operators: small edits that model typical bugs.

`find_sites` lists every place a node can be changed; `apply_site` returns a mutated copy of the
function with exactly one site changed. Site order is the order of an AST walk, so it is
deterministic.
"""

import ast
import copy
from dataclasses import dataclass

BIN_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Div,
    ast.Mod: ast.Mult,
    ast.Pow: ast.Mult,
}
CMP_SWAP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
AUG_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div}
BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass(frozen=True)
class Site:
    index: int
    operator: str
    lineno: int
    detail: str


def _docstring_ids(func: ast.AST) -> set[int]:
    out = set()
    for node in ast.walk(func):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
            val = body[0].value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                out.add(id(val))
    return out


def _options(node: ast.AST, skip: set[int]) -> list[tuple[str, str]]:
    """(operator, detail) pairs this node supports. Order is fixed."""
    if isinstance(node, ast.BinOp) and type(node.op) in BIN_SWAP:
        return [("arith", f"{_sym(node.op)} -> {_sym(BIN_SWAP[type(node.op)]())}")]
    if isinstance(node, ast.AugAssign) and type(node.op) in AUG_SWAP:
        return [("augassign", f"{_sym(node.op)}= -> {_sym(AUG_SWAP[type(node.op)]())}=")]
    if isinstance(node, ast.Compare):
        return [
            ("compare", f"{_sym(op)} -> {_sym(CMP_SWAP[type(op)]())}")
            for op in node.ops
            if type(op) in CMP_SWAP
        ]
    if isinstance(node, ast.BoolOp):
        return [("boolop", f"{_sym(node.op)} -> {_sym(BOOL_SWAP[type(node.op)]())}")]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return [("not", "remove not")]
    if isinstance(node, ast.Constant) and id(node) not in skip:
        v = node.value
        if isinstance(v, bool):
            return [("constant", f"{v} -> {not v}")]
        if isinstance(v, int):
            return [("constant", f"{v} -> {v + 1}")]
        if isinstance(v, str) and v:
            return [("constant", "string -> changed string")]
    if isinstance(node, ast.Return) and node.value is not None:
        if not (isinstance(node.value, ast.Constant) and node.value.value is None):
            return [("return", "return value -> None")]
    if isinstance(node, ast.If | ast.While | ast.IfExp):
        return [("condition", "negate condition")]
    return []


def _sym(op) -> str:
    return {
        "Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "FloorDiv": "//", "Mod": "%",
        "Pow": "**", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=", "Eq": "==", "NotEq": "!=",
        "Is": "is", "IsNot": "is not", "In": "in", "NotIn": "not in", "And": "and", "Or": "or",
    }.get(type(op).__name__, type(op).__name__)  # fmt: skip


def find_sites(func: ast.AST) -> list[Site]:
    skip = _docstring_ids(func)
    sites = []
    for node in ast.walk(func):
        for operator, detail in _options(node, skip):
            sites.append(Site(len(sites), operator, getattr(node, "lineno", 0), detail))
    return sites


def apply_site(func: ast.AST, index: int) -> ast.AST:
    """Return a deep copy of `func` with the index-th site mutated."""
    clone = copy.deepcopy(func)
    skip = _docstring_ids(clone)
    count = 0
    for node in ast.walk(clone):
        opts = _options(node, skip)
        for k in range(len(opts)):
            if count == index:
                _mutate(node, k)
                ast.fix_missing_locations(clone)
                return clone
            count += 1
    raise IndexError(index)


def _mutate(node: ast.AST, k: int) -> None:
    if isinstance(node, ast.BinOp):
        node.op = BIN_SWAP[type(node.op)]()
    elif isinstance(node, ast.AugAssign):
        node.op = AUG_SWAP[type(node.op)]()
    elif isinstance(node, ast.Compare):
        usable = [i for i, op in enumerate(node.ops) if type(op) in CMP_SWAP]
        i = usable[k]
        node.ops[i] = CMP_SWAP[type(node.ops[i])]()
    elif isinstance(node, ast.BoolOp):
        node.op = BOOL_SWAP[type(node.op)]()
    elif isinstance(node, ast.UnaryOp):
        # Replace the node's contents in place with its operand.
        inner = node.operand
        node.__class__, node.__dict__ = inner.__class__, dict(inner.__dict__)
    elif isinstance(node, ast.Constant):
        v = node.value
        node.value = (not v) if isinstance(v, bool) else v + 1 if isinstance(v, int) else v + "_x"
    elif isinstance(node, ast.Return):
        node.value = ast.Constant(value=None)
    elif isinstance(node, ast.If | ast.While | ast.IfExp):
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
