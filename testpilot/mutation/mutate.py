"""Build the mutants of one unit: a seeded sample of at most MAX_MUTANTS single-edit variants."""

import ast
import random
from dataclasses import dataclass
from pathlib import Path

from testpilot.context.builder import iter_functions
from testpilot.mutation.operators import apply_site, find_sites

MAX_MUTANTS = 40
HOLDOUT_SEED = 20240607


@dataclass
class Mutant:
    id: str  # "<unit sha>#<site index>"
    operator: str
    lineno: int
    detail: str
    code: str  # the whole mutated file


def unit_tree(file_text: str, qualname: str) -> tuple[ast.Module, ast.AST]:
    tree = ast.parse(file_text)
    func = dict(iter_functions(tree))[qualname]
    return tree, func


def baseline_code(file_text: str) -> str:
    """The unmutated file as the engine would write it (ast.unparse drops comments)."""
    return ast.unparse(ast.parse(file_text)) + "\n"


def make_mutants(
    file_text: str, qualname: str, key: str, seed: int = 0, limit: int = MAX_MUTANTS
) -> list[Mutant]:
    tree, func = unit_tree(file_text, qualname)
    sites = find_sites(func)
    if len(sites) > limit:
        # Seed on the unit key so the same unit always gets the same sample.
        rng = random.Random(f"{seed}:{key}")
        sites = sorted(rng.sample(sites, limit), key=lambda s: s.index)
    mutants = []
    for site in sites:
        mutated = apply_site(func, site.index)
        holder = _parent_body(tree, func)
        pos = holder.index(func)
        holder[pos] = mutated
        try:
            code = ast.unparse(tree) + "\n"
        finally:
            holder[pos] = func
        mutants.append(Mutant(f"{key}#{site.index}", site.operator, site.lineno, site.detail, code))
    return mutants


def _parent_body(tree: ast.Module, func: ast.AST) -> list:
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and func in body:
            return body
    raise ValueError("function not found")


def shown_ids(mutants: list[Mutant], key: str) -> set[str]:
    """The half of a unit's mutants that mutation-guided generation may see.

    The rest are held out for grading. Mutants with the same description stay in one half,
    because feedback naming one would name the other too. The held-out half is filled first.
    """
    groups: dict[tuple, list[str]] = {}
    for m in mutants:
        groups.setdefault((m.lineno, m.operator, m.detail), []).append(m.id)
    order = list(groups.values())
    random.Random(f"holdout:{HOLDOUT_SEED}:{key}").shuffle(order)
    shown: list[str] = []
    n_held = 0
    for ids in order:
        if n_held <= len(shown):
            n_held += len(ids)
        else:
            shown += ids
    return set(shown)


def read_file(repo_dir: Path, rel: str) -> str:
    return (repo_dir / rel).read_text(encoding="utf-8", errors="replace")
