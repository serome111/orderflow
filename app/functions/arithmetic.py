"""Basic arithmetic transformations."""

from __future__ import annotations

from ._helpers import coerce_number
from .registry import register


@register()
def add(var1: object, var2: object) -> float | int:
    """Return the numeric sum of ``var1`` and ``var2``."""

    n1 = coerce_number(var1, func_name="add", arg_name="var1")
    n2 = coerce_number(var2, func_name="add", arg_name="var2")
    result = n1 + n2
    if isinstance(n1, int) and isinstance(n2, int):
        return int(result)
    return result


@register()
def subtract(var1: object, var2: object) -> float | int:
    """Return the numeric result of ``var1 - var2``."""

    n1 = coerce_number(var1, func_name="subtract", arg_name="var1")
    n2 = coerce_number(var2, func_name="subtract", arg_name="var2")
    result = n1 - n2
    if isinstance(n1, int) and isinstance(n2, int):
        return int(result)
    return result
