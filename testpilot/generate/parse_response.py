"""Pull one pytest file out of a model reply, and refuse anything that is not valid Python."""

import ast
import re

FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)


def extract_tests(reply: str) -> str | None:
    """Return the test file text, or None if the reply has no usable test code."""
    blocks = FENCE.findall(reply)
    if not blocks:
        # Unclosed fence (reply cut off) or bare code.
        tail = reply.split("```python", 1)[-1] if "```python" in reply else reply
        blocks = [tail.replace("```", "")]
    code = max(blocks, key=len).strip("\n") + "\n"
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    has_test = any(
        isinstance(n, ast.FunctionDef) and n.name.startswith("test") for n in ast.walk(tree)
    )
    return code if has_test else None
