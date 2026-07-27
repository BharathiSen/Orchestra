from __future__ import annotations

import ast
import operator
from typing import Any

from app.tools.base import BaseTool

# Safe subset of AST operators — never eval() user strings.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    # Python 3.11 still may emit Num in some edge paths; keep defensive.
    if isinstance(node, ast.Num):  # type: ignore[attr-defined]
        return float(node.n)  # type: ignore[attr-defined]
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type in {ast.Div, ast.FloorDiv, ast.Mod} and right == 0:
            raise ValueError("Division by zero")
        if op_type is ast.Pow and abs(right) > 10:
            raise ValueError("Exponent too large")
        return float(_BIN_OPS[op_type](left, right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return float(_UNARY_OPS[op_type](_safe_eval(node.operand)))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


class CalculatorTool(BaseTool):
    """Evaluate simple arithmetic expressions safely (no eval of code)."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Evaluate a basic math expression and return the numeric result. "
            "Use for arithmetic like 2+5, (12*8)/3, or 2**10. "
            "Do not use for word problems that need reasoning — just for calculation."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression using + - * / // % ** and parentheses.",
                }
            },
            "required": ["expression"],
            "additionalProperties": False,
        }

    def execute(self, **kwargs: Any) -> str:
        expression = str(kwargs.get("expression", "")).strip()
        if not expression:
            raise ValueError("expression is required")
        if len(expression) > 200:
            raise ValueError("expression is too long")

        try:
            tree = ast.parse(expression, mode="eval")
            value = _safe_eval(tree)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Could not evaluate expression '{expression}': {exc}") from exc

        # Prefer clean ints when exact.
        if float(value).is_integer():
            return str(int(value))
        return str(value)
