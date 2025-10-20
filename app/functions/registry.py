"""Lightweight registry to keep transformation functions discoverable."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict

Registry = Dict[str, Callable[..., Any]]
_registry: Registry = {}


def register(name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to register a callable in the registry.

    Parameters
    ----------
    name:
        Optional alias. Defaults to ``func.__name__`` in lowercase.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        key = (name or func.__name__).lower()
        if key in _registry:
            raise ValueError(f"Function '{key}' already registered.")
        _registry[key] = func
        return func

    return decorator


def get_function(name: str) -> Callable[..., Any]:
    try:
        return _registry[name.lower()]
    except KeyError as exc:
        available = ", ".join(sorted(_registry))
        raise KeyError(
            f"Function '{name}' is not registered. Available: {available or 'none'}."
        ) from exc


def call_function(name: str, *args: Any, **kwargs: Any) -> Any:
    func = get_function(name)
    return func(*args, **kwargs)


def list_functions() -> list[str]:
    return sorted(_registry)
