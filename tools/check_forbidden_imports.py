#!/usr/bin/env python3
"""Fail pre-commit if forbidden imports are introduced outside allowlist."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ALLOWLIST_PATH = Path("tools/forbidden_import_allowlist.txt")


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
        if path.startswith("tests/") or path.startswith("tests_unit/"):
            continue
        if path in allowlist:
            continue
        offending.append(line)
    return offending


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: check_forbidden_imports.py <module> [<module> ...]", file=sys.stderr)
        return 2

    allowlist = load_allowlist()
    failures: list[str] = []
    for module in argv[1:]:
        failures.extend(check_module(module, allowlist))

    if failures:
        print("Forbidden imports detected. Review the following lines:\n", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        if allowlist:
            print(
                "\nIf these imports are intentional, add the file path to",
                ALLOWLIST_PATH,
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
