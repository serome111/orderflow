"""Shared utilities for transformation functions."""

from __future__ import annotations


def coerce_number(value: object, *, func_name: str, arg_name: str) -> float | int:
    """
    Convert ``value`` into ``int`` or ``float``.

    Raises
    ------
    ValueError
        If conversion is not possible.
    """

    if value is None:
        raise ValueError(f"{func_name}: '{arg_name}' is required.")

    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        raise ValueError(f"{func_name}: '{arg_name}' cannot be empty.")

    try:
        number = int(text)
    except ValueError:
        try:
            number = float(text)
        except ValueError as exc:
            raise ValueError(
                f"{func_name}: '{arg_name}' must be numeric (got {value!r})."
            ) from exc
    return number
