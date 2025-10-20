"""Text related transformations."""

from __future__ import annotations

from .registry import register


@register()
def to_lowercase(var1: object, var2: object | None = None) -> str:
    """Convert ``var1`` to lowercase; ``var2`` is ignored."""

    if var1 is None:
        raise ValueError("to_lowercase: 'var1' is required.")
    return str(var1).lower()
