from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_registered_functions_are_available() -> None:
    from app.functions import call_function, list_functions

    available = list_functions()
    assert "add" in available
    assert "subtract" in available
    assert "to_lowercase" in available

    assert call_function("add", 2, 3) == 5
    assert call_function("subtract", 5, 2) == 3
    assert call_function("to_lowercase", "HOLA") == "hola"


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("add", "5", "7"), "12"),
        (("subtract", "10", "8"), "2"),
        (("to_lowercase", "HOLA"), "hola"),
    ],
)
def test_cli_executes_registered_function(args: tuple[str, ...], expected: str) -> None:
    result = run_cli(*args)
    assert result.returncode == 0
    assert result.stdout.strip() == expected
    assert result.stderr == ""


def test_cli_list_option_outputs_registered_functions() -> None:
    result = run_cli("--list")
    assert result.returncode == 0
    output = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    assert {"add", "subtract", "to_lowercase"}.issubset(output)
    assert result.stderr == ""
