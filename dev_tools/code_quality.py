#!/usr/bin/env python3
"""Code quality checks for Egregora.

This script runs comprehensive code quality checks using multiple tools:
- vulture: Dead code detection
- radon: Complexity analysis
- bandit: Security scanning
- deptry: Dependency analysis
- pytest-cov: Test coverage
- ruff: Linting

Usage:
    python dev_tools/code_quality.py                # Run all checks
    python dev_tools/code_quality.py --quick        # Run only fast checks
    python dev_tools/code_quality.py --check vulture  # Run specific check
    python dev_tools/code_quality.py --ci           # CI mode (fail on issues)
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from enum import Enum


class CheckResult(Enum):
    """Result of a quality check."""

    PASS = "✅"
    WARN = "⚠️"
    FAIL = "❌"
    SKIP = "⏭️"


@dataclass
class CheckOutput:
    """Output from a quality check."""

    name: str
    result: CheckResult
    message: str
    details: str = ""
    exit_code: int = 0


def run_command(cmd: list[str], description: str) -> CheckOutput:
    """Run a command and capture output."""
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode == 0:
            return CheckOutput(
                name=description,
                result=CheckResult.PASS,
                message="All checks passed",
                details=result.stdout[:500] if result.stdout else "",
                exit_code=0,
            )
        return CheckOutput(
            name=description,
            result=CheckResult.FAIL,
            message=f"Failed with exit code {result.returncode}",
            details=result.stdout[:1000] if result.stdout else result.stderr[:1000],
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return CheckOutput(
            name=description,
            result=CheckResult.FAIL,
            message="Timeout after 5 minutes",
            exit_code=124,
        )
    except FileNotFoundError:
        return CheckOutput(
            name=description,
            result=CheckResult.SKIP,
            message="Tool not installed (run: uv sync --all-extras)",
            exit_code=127,
        )
    except Exception as e:
        return CheckOutput(
            name=description,
            result=CheckResult.FAIL,
            message=f"Error: {e}",
            exit_code=1,
        )


def check_dead_code() -> CheckOutput:
    """Check for dead code using vulture."""
    return run_command(
        ["uv", "run", "vulture", "src", "tests", "--min-confidence", "80"],
        "Dead Code Detection (vulture)",
    )


def check_complexity() -> CheckOutput:
    """Check code complexity using radon."""
    result = run_command(
        ["uv", "run", "radon", "cc", "src/egregora", "-s", "-n", "D", "--total-average"],
        "Complexity Analysis (radon)",
    )

    # radon returns 0 even with D+ grade functions, so we need to check output
    if result.result == CheckResult.PASS and result.details:
        # Check if any D or F grade functions are in output
        if " - D " in result.details or " - F " in result.details:
            return CheckOutput(
                name=result.name,
                result=CheckResult.FAIL,
                message="Found D or F grade functions (complexity >= 21)",
                details=result.details,
                exit_code=1,
            )

    return result


def check_security() -> CheckOutput:
    """Check security issues using bandit."""
    return run_command(
        ["uv", "run", "bandit", "-r", "src", "--severity-level", "medium", "-q"],
        "Security Scan (bandit)",
    )


def check_dependencies() -> CheckOutput:
    """Check dependency issues using deptry."""
    result = run_command(
        ["uv", "run", "deptry", "."],
        "Dependency Analysis (deptry)",
    )

    # deptry has many false positives, so we warn instead of fail
    if result.result == CheckResult.FAIL:
        # Count real issues (not internal imports)
        details = result.details
        real_issues = [
            line for line in details.split("\n") if "DEP" in line and "'egregora' imported" not in line
        ]

        if len(real_issues) < 10:  # Threshold for real issues
            return CheckOutput(
                name=result.name,
                result=CheckResult.WARN,
                message=f"Found {len(real_issues)} dependency issues (may be false positives)",
                details=result.details,
                exit_code=0,
            )

    return result


def check_coverage(threshold: int = 40) -> CheckOutput:
    """Check test coverage using pytest-cov."""
    result = run_command(
        [
            "uv",
            "run",
            "pytest",
            "tests/unit/",
            "--cov=src/egregora",
            "--cov-report=term-missing:skip-covered",
            "--cov-fail-under",
            str(threshold),
            "-q",
            "--tb=no",
        ],
        f"Test Coverage (pytest-cov >= {threshold}%)",
    )

    # pytest-cov output goes to stderr, not stdout
    if result.result == CheckResult.PASS:
        return result

    # If failed, check if it's coverage or test failure
    if "test session starts" in result.details or "FAILED" in result.details:
        return CheckOutput(
            name=result.name,
            result=CheckResult.FAIL,
            message="Test failures detected",
            details=result.details,
            exit_code=result.exit_code,
        )

    return result


def check_linting() -> CheckOutput:
    """Check linting using ruff."""
    return run_command(
        ["uv", "run", "ruff", "check", ".", "--output-format=concise"],
        "Linting (ruff)",
    )


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def print_result(output: CheckOutput) -> None:
    """Print check result."""
    icon = output.result.value
    print(f"{icon} {output.name}: {output.message}")

    if output.details and output.result != CheckResult.PASS:
        # Print first few lines of details
        lines = output.details.strip().split("\n")[:10]
        for line in lines:
            print(f"  {line}")
        total_lines = len(output.details.split("\n"))
        if total_lines > 10:
            remaining = total_lines - 10
            print(f"  ... ({remaining} more lines)")


def main() -> int:
    """Run code quality checks."""
    import argparse

    parser = argparse.ArgumentParser(description="Run code quality checks")
    parser.add_argument("--quick", action="store_true", help="Run only fast checks")
    parser.add_argument("--check", type=str, help="Run specific check (vulture, radon, bandit, etc.)")
    parser.add_argument("--ci", action="store_true", help="CI mode (fail on any issues)")
    parser.add_argument(
        "--coverage-threshold", type=int, default=40, help="Minimum coverage percentage (default: 40)"
    )

    args = parser.parse_args()

    print_header("🔍 Egregora Code Quality Checks")

    # Define all checks
    all_checks = {
        "vulture": check_dead_code,
        "radon": check_complexity,
        "bandit": check_security,
        "deptry": check_dependencies,
        "coverage": lambda: check_coverage(args.coverage_threshold),
        "ruff": check_linting,
    }

    # Determine which checks to run
    if args.check:
        if args.check not in all_checks:
            return 1
        checks_to_run = {args.check: all_checks[args.check]}
    elif args.quick:
        # Quick checks: linting, dead code, complexity
        checks_to_run = {
            "ruff": all_checks["ruff"],
            "vulture": all_checks["vulture"],
            "radon": all_checks["radon"],
        }
    else:
        # Run all checks
        checks_to_run = all_checks

    # Run checks
    results: list[CheckOutput] = []
    for check_func in checks_to_run.values():
        result = check_func()
        results.append(result)
        print_result(result)

    # Summary
    print_header("📊 Summary")

    sum(1 for r in results if r.result == CheckResult.PASS)
    warned = sum(1 for r in results if r.result == CheckResult.WARN)
    failed = sum(1 for r in results if r.result == CheckResult.FAIL)
    sum(1 for r in results if r.result == CheckResult.SKIP)

    len(results)

    # Determine exit code
    if args.ci:
        # In CI mode, warnings also count as failures
        if failed > 0 or warned > 0:
            return 1
    # In normal mode, only failures count
    elif failed > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
