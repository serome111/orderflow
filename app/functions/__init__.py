"""
Dynamic registry and auto-discovery of transformation functions.

Any module inside this package can register functions using the decorator
provided by :mod:`app.functions.registry`. When this package is imported we
scan sibling modules and import them, triggering registrations automatically.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from .registry import (
    call_function,
    get_function,
    list_functions,
    register,
)

__all__ = [
    "register",
    "call_function",
    "get_function",
    "list_functions",
]


def _auto_discover() -> None:
    """Import every peer module to trigger registration side-effects."""
    package_path = Path(__file__).resolve().parent
    for module_info in pkgutil.iter_modules([str(package_path)]):
        module_name = module_info.name
        if module_name.startswith("_") or module_name == "registry":
            continue
        importlib.import_module(f"{__name__}.{module_name}")


_auto_discover()
