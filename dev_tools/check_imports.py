#!/usr/bin/env python3
"""Fail pre-commit if forbidden imports are introduced outside allowlist."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ALLOWLIST_PATH = Path("dev_tools/import_allowlist.txt")


def load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        return set()
    return {
        line.strip()
        for line in ALLOWLIST_PATH.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def check_module(module: str, allowlist: set[str]) -> list[str]:
    pattern = rf"(^|\\s)import\\s+{module}\\b|(^|\\s)from\\s+{module}\\b"
    result = subprocess.run(
        [
            "git",
            "grep",
            "-nE",
            pattern,
            "--",
            ".",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    offending: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        path, *_ = line.split(":", 2)
        if path.startswith(("tests/", "tests_unit/")):
            continue
        if path in allowlist:
            continue
        offending.append(line)
    return offending


MIN_ARGS = 2
USAGE_ERROR_CODE = 2
FAILURE_ERROR_CODE = 1
SUCCESS_ERROR_CODE = 0


def main(argv: list[str]) -> int:
    if len(argv) < MIN_ARGS:
        return USAGE_ERROR_CODE

    allowlist = load_allowlist()
    failures: list[str] = []
    for module in argv[1:]:
        failures.extend(check_module(module, allowlist))

    if failures:
        if allowlist:
            pass
        return FAILURE_ERROR_CODE
    return SUCCESS_ERROR_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
