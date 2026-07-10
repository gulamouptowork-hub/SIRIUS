from __future__ import annotations

import ast
import math
import operator

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_FUNCTIONS = {
    name: getattr(math, name)
    for name in (
        "sqrt", "sin", "cos", "tan", "asin", "acos", "atan",
        "log", "log2", "log10", "exp", "floor", "ceil", "factorial", "degrees", "radians",
    )
}
_FUNCTIONS.update({"abs": abs, "round": round, "min": min, "max": max})
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def calculate(expression: str) -> float:
    """Safely evaluate an arithmetic expression (AST whitelist, no eval)."""
    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
        and not node.keywords
    ):
        return _FUNCTIONS[node.func.id](*(_eval(arg) for arg in node.args))
    raise ValueError(f"Unsupported expression element: {ast.dump(node)[:80]}")
