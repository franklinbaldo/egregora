"""Diagnostic utilities for verifying Egregora setup.

This module provides health checks for dependencies, configuration,
and system requirements. Used by the `egregora doctor` CLI command.

All imports are lazy (inside functions) to allow diagnostics to run even
when dependencies are missing - this is the whole point of diagnostics!

Usage:
    from egregora.cli.diagnostics import run_diagnostics, DiagnosticResult

    results = run_diagnostics()
    for result in results:
        print(f"{result.check}: {result.status}")
"""

import importlib.util
import os
import shutil
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from egregora.config import find_egregora_config, load_egregora_config
from egregora.input_adapters import list_adapters

# Constants
MIN_API_KEY_LENGTH_FOR_MASKING = 12  # Minimum length to safely mask API key (8 + 4 chars)


class HealthStatus(str, Enum):
    """Health check status levels."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    """Result of a diagnostic health check.

    Attributes:
        check: Name of the check (e.g., "API Key")
        status: Health status (OK, WARNING, ERROR, INFO)
        message: Human-readable message
        details: Optional additional details

    """

    check: str
    status: HealthStatus
    message: str
    details: dict[str, Any] | None = None


def check_python_version() -> DiagnosticResult:
    """Check if Python version meets minimum requirement (3.12+)."""
    version = sys.version_info
    if version >= (3, 12):
        return DiagnosticResult(
            check="Python Version",
            status=HealthStatus.OK,
            message=f"Python {version.major}.{version.minor}.{version.micro}",
        )
    return DiagnosticResult(
        check="Python Version",
        status=HealthStatus.ERROR,
        message=f"Python {version.major}.{version.minor}.{version.micro} (requires 3.12+)",
    )


def check_required_packages() -> DiagnosticResult:
    """Check if required packages are installed."""
    required = [
        "ibis",
        "duckdb",
        "pydantic",
        "pydantic_ai",
        "google.genai",
        "typer",
        "rich",
    ]

    missing = []
    for package in required:
        try:
            # Try importing the module to check if it's available
            importlib.import_module(package)
        except ImportError:
            missing.append(package)

    if not missing:
        return DiagnosticResult(
            check="Required Packages",
            status=HealthStatus.OK,
            message=f"All {len(required)} required packages installed",
        )

    return DiagnosticResult(
        check="Required Packages",
        status=HealthStatus.ERROR,
        message=f"Missing packages: {', '.join(missing)}",
        details={"missing": missing},
    )


def check_api_key() -> DiagnosticResult:
    """Check if GOOGLE_API_KEY is configured."""
    # Avoid importing from egregora.config to keep diagnostics dependency-free
    # as egregora.config imports pydantic/yaml which might be missing.
    api_key = os.getenv("GOOGLE_API_KEY")

    if api_key:
        # Mask the key for security
        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > MIN_API_KEY_LENGTH_FOR_MASKING else "***"
        return DiagnosticResult(
            check="API Key",
            status=HealthStatus.OK,
            message=f"GOOGLE_API_KEY set ({masked})",
        )

    return DiagnosticResult(
        check="API Key",
        status=HealthStatus.WARNING,
        message="GOOGLE_API_KEY not set (required for enrichment and generation)",
        details={"env_var": "GOOGLE_API_KEY"},
    )


def check_duckdb_zipfs() -> DiagnosticResult:
    """Check if DuckDB zipfs extension is available for streaming ZIP reads."""
    # Lazy import - allows doctor command to run even if duckdb not installed
    try:
        duckdb = importlib.import_module("duckdb")
    except ImportError:
        return DiagnosticResult(
            check="DuckDB ZipFS Extension",
            status=HealthStatus.INFO,
            message="DuckDB not installed",
            details={"missing_package": "duckdb"},
        )

    try:
        conn = duckdb.connect(":memory:")

        # Try to install zipfs extension from community repository
        try:
            conn.execute("INSTALL zipfs FROM community")
            conn.execute("LOAD zipfs")

            # Verify extension is loaded
            result = conn.execute(
                "SELECT extension_name, loaded FROM duckdb_extensions() WHERE extension_name = 'zipfs'"
            ).fetchone()

            if result and result[1]:  # loaded = True
                return DiagnosticResult(
                    check="DuckDB ZipFS Extension",
                    status=HealthStatus.OK,
                    message="ZipFS extension available (enables vectorized ZIP parsing)",
                    details={"benefit": "WhatsApp adapter can use fully vectorized parsing"},
                )

            return DiagnosticResult(
                check="DuckDB ZipFS Extension",
                status=HealthStatus.INFO,
                message="ZipFS extension installed but not loaded",
            )

        except duckdb.IOException:
            # Extension not available (requires DuckDB 1.4.2+)
            return DiagnosticResult(
                check="DuckDB ZipFS Extension",
                status=HealthStatus.INFO,
                message="ZipFS not available (requires DuckDB 1.4.2+, using Python fallback)",
                details={
                    "workaround": "WhatsApp adapter uses hybrid Python+DuckDB approach",
                    "repo": "https://github.com/isaacbrodsky/duckdb-zipfs",
                },
            )

        finally:
            conn.close()

    except Exception as e:
        # Diagnostic check failure shouldn't crash the tool, just report as INFO/ERROR
        return DiagnosticResult(
            check="DuckDB ZipFS Extension",
            status=HealthStatus.INFO,
            message=f"Failed to check zipfs extension: {e}",
        )


def check_git() -> DiagnosticResult:
    """Check if git is available for code_ref tracking."""
    try:
        # Resolve full path to git to avoid S607 (partial executable path)
        git_path = shutil.which("git")
        if not git_path:
            msg = "git executable not found"
            raise FileNotFoundError(msg)

        result = subprocess.run(  # nosec B603
            [git_path, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )  # nosec B603
        version = result.stdout.strip()
        return DiagnosticResult(
            check="Git",
            status=HealthStatus.OK,
            message=version,
        )

    except subprocess.CalledProcessError:
        return DiagnosticResult(
            check="Git",
            status=HealthStatus.WARNING,
            message="Git not available (code_ref tracking disabled)",
        )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return DiagnosticResult(
            check="Git",
            status=HealthStatus.WARNING,
            message="Git not found in PATH (code_ref tracking disabled)",
        )


def check_cache_directory() -> DiagnosticResult:
    """Check if cache directory is writable."""
    cache_dir = Path(".egregora-cache")

    try:
        # Try creating cache directory
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Try writing a test file
        test_file = cache_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()

        # Check size if exists
        if cache_dir.exists():
            total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
            size_mb = total_size / (1024**2)

            return DiagnosticResult(
                check="Cache Directory",
                status=HealthStatus.OK,
                message=f"Writable at {cache_dir.absolute()} ({size_mb:.1f} MB)",
                details={"path": str(cache_dir.absolute()), "size_mb": size_mb},
            )

        return DiagnosticResult(
            check="Cache Directory",
            status=HealthStatus.OK,
            message=f"Writable at {cache_dir.absolute()}",
        )

    except OSError as e:
        return DiagnosticResult(
            check="Cache Directory",
            status=HealthStatus.ERROR,
            message=f"Cannot write to {cache_dir.absolute()}: {e}",
        )


def check_egregora_config() -> DiagnosticResult:
    """Check if .egregora.toml exists and is valid."""
    config_file = Path(".egregora.toml")
    # find_egregora_config returns path or None
    config_path = find_egregora_config(config_file.parent)

    if not config_path:
        return DiagnosticResult(
            check="Egregora Config",
            status=HealthStatus.INFO,
            message="No .egregora.toml (will use defaults)",
        )

    try:
        # Try loading config
        config = load_egregora_config(config_file.parent)  # Pass site root

        return DiagnosticResult(
            check="Egregora Config",
            status=HealthStatus.OK,
            message=f"Valid config at {config_path}",
            details={
                "writer_model": config.models.writer,
                "rag_enabled": config.rag.enabled,
                "pipeline_step_unit": config.pipeline.step_unit,
            },
        )

    except Exception as e:
        # Catch configuration loading errors (validation, parsing, etc.)
        return DiagnosticResult(
            check="Egregora Config",
            status=HealthStatus.ERROR,
            message=f"Invalid config: {e}",
        )


def check_adapters() -> DiagnosticResult:
    """Check available source adapters."""
    try:
        sources = list_adapters()

        if sources:
            return DiagnosticResult(
                check="Source Adapters",
                status=HealthStatus.OK,
                message=f"{len(sources)} adapters available: {', '.join(sources)}",
                details={"adapters": sources},
            )

        return DiagnosticResult(
            check="Source Adapters",
            status=HealthStatus.ERROR,
            message="No adapters registered",
        )

    except Exception as e:
        # Adapter listing failure shouldn't crash diagnostics
        return DiagnosticResult(
            check="Source Adapters",
            status=HealthStatus.ERROR,
            message=f"Failed to list adapters: {e}",
        )


def run_diagnostics() -> list[DiagnosticResult]:
    """Run all diagnostic checks.

    Returns:
        List of diagnostic results, one per check

    Example:
        >>> results = run_diagnostics()
        >>> for result in results:
        ...     print(f"{result.check}: {result.status.value}")

    """
    checks = [
        check_python_version,
        check_required_packages,
        check_api_key,
        check_duckdb_zipfs,
        check_git,
        check_cache_directory,
        check_egregora_config,
        check_adapters,
    ]

    results = []
    for check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            # Catch-all for unexpected check failures to ensure report is generated
            check_name = getattr(check_func, "__name__", "Unknown Check")
            check_name = check_name.replace("check_", "").replace("_", " ").title()
            results.append(
                DiagnosticResult(
                    check=check_name,
                    status=HealthStatus.ERROR,
                    message=f"Check failed: {e}",
                )
            )

    return results
