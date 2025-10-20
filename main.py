from __future__ import annotations

import argparse
import ast
import sys
from typing import Any, Sequence

from app.functions import call_function, list_functions


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute a registered transformation function."
    )
    parser.add_argument(
        "function_name",
        nargs="?",
        help="Name of the function to execute (e.g. 'add').",
    )
    parser.add_argument(
        "var1",
        nargs="?",
        help="First parameter for the function.",
    )
    parser.add_argument(
        "var2",
        nargs="?",
        help="Optional second parameter for the function.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="show_list",
        help="Print the registered functions and exit.",
    )
    args = parser.parse_args(argv)

    if args.show_list:
        return args

    if args.function_name is None or args.var1 is None:
        parser.error("function_name and var1 are required (unless --list is used).")

    return args


def coerce_value(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        lowered = raw.lower()
        if lowered == "none":
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return raw


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.show_list:
        for name in list_functions():
            print(name)
        return 0

    var1 = coerce_value(args.var1)
    var2 = coerce_value(args.var2)

    try:
        result = call_function(args.function_name, var1, var2)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
