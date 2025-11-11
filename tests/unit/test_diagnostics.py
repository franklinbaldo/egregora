"""Tests for diagnostic utilities (egregora doctor command)."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import pytest

from egregora.diagnostics import (
    DiagnosticResult,
    HealthStatus,
    check_adapters,
    check_api_key,
    check_cache_directory,
    check_duckdb_extensions,
    check_egregora_config,
    check_git,
    check_python_version,
    check_required_packages,
    run_diagnostics,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_status_values(self) -> None:
        """HealthStatus has expected values."""
        assert HealthStatus.OK == "ok"
        assert HealthStatus.WARNING == "warning"
        assert HealthStatus.ERROR == "error"
        assert HealthStatus.INFO == "info"


class TestDiagnosticResult:
    """Tests for DiagnosticResult dataclass."""

    def test_create_result_minimal(self) -> None:
        """DiagnosticResult can be created with minimal fields."""
        result = DiagnosticResult(
            check="Test Check",
            status=HealthStatus.OK,
            message="Test message",
        )

        assert result.check == "Test Check"
        assert result.status == HealthStatus.OK
        assert result.message == "Test message"
        assert result.details is None

    def test_create_result_with_details(self) -> None:
        """DiagnosticResult can include optional details."""
        result = DiagnosticResult(
            check="Test Check",
            status=HealthStatus.ERROR,
            message="Test error",
            details={"key": "value", "count": 42},
        )

        assert result.details == {"key": "value", "count": 42}

    def test_result_is_frozen(self) -> None:
        """DiagnosticResult is immutable (frozen dataclass)."""
        result = DiagnosticResult(
            check="Test",
            status=HealthStatus.OK,
            message="Message",
        )

        with pytest.raises(AttributeError):
            result.status = HealthStatus.ERROR  # type: ignore[misc]


class TestCheckPythonVersion:
    """Tests for check_python_version()."""

    def test_python_version_meets_requirement(self) -> None:
        """Returns OK if Python >= 3.12."""
        result = check_python_version()

        # Current Python should be 3.12+ (project requirement)
        assert result.check == "Python Version"
        assert result.status == HealthStatus.OK
        assert "Python 3.12" in result.message or "Python 3.13" in result.message


class TestCheckRequiredPackages:
    """Tests for check_required_packages()."""

    def test_all_packages_installed(self) -> None:
        """Returns OK when all required packages are available."""
        result = check_required_packages()

        # In test environment, all packages should be installed
        assert result.check == "Required Packages"
        assert result.status == HealthStatus.OK
        assert "7 required packages installed" in result.message

    @patch("egregora.diagnostics.importlib.import_module")
    def test_missing_packages(self, mock_import: MagicMock) -> None:
        """Returns ERROR when packages are missing."""

        # Mock importlib to raise ImportError for specific packages
        def mock_import_func(name: str) -> None:
            if name in ("ibis", "duckdb"):
                msg = f"No module named '{name}'"
                raise ImportError(msg)

        mock_import.side_effect = mock_import_func

        result = check_required_packages()

        assert result.status == HealthStatus.ERROR
        assert "Missing packages" in result.message
        assert result.details is not None
        assert "missing" in result.details


class TestCheckApiKey:
    """Tests for check_api_key()."""

    def test_api_key_set(self) -> None:
        """Returns OK when GOOGLE_API_KEY is set."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key-12345678abcd"}):
            result = check_api_key()

            assert result.check == "API Key"
            assert result.status == HealthStatus.OK
            assert "GOOGLE_API_KEY set" in result.message
            # Check key is masked - format is "first8...last4"
            assert "..." in result.message  # Contains ellipsis for masking

    def test_api_key_not_set(self) -> None:
        """Returns WARNING when GOOGLE_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = check_api_key()

            assert result.check == "API Key"
            assert result.status == HealthStatus.WARNING
            assert "GOOGLE_API_KEY not set" in result.message
            assert result.details is not None
            assert result.details["env_var"] == "GOOGLE_API_KEY"

    def test_api_key_masking_short_key(self) -> None:
        """Short API keys are fully masked."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "short"}):
            result = check_api_key()

            assert result.status == HealthStatus.OK
            assert "***" in result.message
            assert "short" not in result.message


class TestCheckDuckDBExtensions:
    """Tests for check_duckdb_extensions()."""

    def test_vss_extension_available(self) -> None:
        """Returns OK when VSS extension is available (may fail in CI)."""
        result = check_duckdb_extensions()

        assert result.check == "DuckDB VSS Extension"
        # Can be OK or WARNING depending on environment
        assert result.status in (HealthStatus.OK, HealthStatus.WARNING)

    @patch("duckdb.connect")
    def test_vss_extension_io_error(self, mock_connect: MagicMock) -> None:
        """Returns WARNING when VSS extension is not available."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Mock VSS installation failure
        mock_conn.execute.side_effect = duckdb.IOException("Extension not available")

        result = check_duckdb_extensions()

        assert result.status == HealthStatus.WARNING
        assert "not available" in result.message
        assert result.details is not None
        assert "workaround" in result.details

    @patch("duckdb.connect")
    def test_duckdb_connection_error(self, mock_connect: MagicMock) -> None:
        """Returns ERROR when DuckDB connection fails."""
        mock_connect.side_effect = Exception("Connection failed")

        result = check_duckdb_extensions()

        assert result.status == HealthStatus.ERROR
        assert "Failed to check VSS extension" in result.message


class TestCheckGit:
    """Tests for check_git()."""

    def test_git_available(self) -> None:
        """Returns OK when git is available."""
        result = check_git()

        assert result.check == "Git"
        # Git should be available in most environments
        if result.status == HealthStatus.OK:
            assert "git version" in result.message

    @patch("egregora.diagnostics.subprocess.run")
    def test_git_not_found(self, mock_run: MagicMock) -> None:
        """Returns WARNING when git is not found."""
        mock_run.side_effect = FileNotFoundError("git not found")

        result = check_git()

        assert result.status == HealthStatus.WARNING
        assert "Git not found" in result.message

    @patch("egregora.diagnostics.subprocess.run")
    def test_git_command_error(self, mock_run: MagicMock) -> None:
        """Returns WARNING when git command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        result = check_git()

        assert result.status == HealthStatus.WARNING
        assert "Git not available" in result.message

    @patch("egregora.diagnostics.subprocess.run")
    def test_git_timeout(self, mock_run: MagicMock) -> None:
        """Returns WARNING when git command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 2)

        result = check_git()

        assert result.status == HealthStatus.WARNING
        assert "Git not found" in result.message


class TestCheckCacheDirectory:
    """Tests for check_cache_directory()."""

    def test_cache_directory_writable(self, tmp_path: Path) -> None:
        """Returns OK when cache directory is writable."""
        # Change to temp directory
        original_cwd = Path.cwd()
        os.chdir(tmp_path)

        try:
            result = check_cache_directory()

            assert result.check == "Cache Directory"
            assert result.status == HealthStatus.OK
            assert "Writable" in result.message
            assert ".egregora-cache" in result.message

            # Cache directory should have been created
            assert (tmp_path / ".egregora-cache").exists()

        finally:
            os.chdir(original_cwd)

    @patch("egregora.diagnostics.Path.mkdir")
    def test_cache_directory_creation_fails(self, mock_mkdir: MagicMock) -> None:
        """Returns ERROR when cache directory cannot be created."""
        mock_mkdir.side_effect = OSError("Permission denied")

        result = check_cache_directory()

        assert result.status == HealthStatus.ERROR
        assert "Cannot write" in result.message


class TestCheckEgregoraConfig:
    """Tests for check_egregora_config()."""

    def test_no_config_file(self, tmp_path: Path) -> None:
        """Returns INFO when no config file exists."""
        original_cwd = Path.cwd()
        os.chdir(tmp_path)

        try:
            result = check_egregora_config()

            assert result.check == "Egregora Config"
            assert result.status == HealthStatus.INFO
            assert "No .egregora/config.yml" in result.message

        finally:
            os.chdir(original_cwd)

    @patch("egregora.config.load_egregora_config")
    def test_valid_config_file(self, mock_load_config: MagicMock, tmp_path: Path) -> None:
        """Returns OK when valid config file exists."""
        # Mock successful config loading
        mock_config = MagicMock()
        mock_config.models.writer = "google-gla:gemini-2.0-flash-exp"
        mock_config.rag.enabled = True
        mock_config.pipeline.step_unit = "messages"
        mock_load_config.return_value = mock_config

        original_cwd = Path.cwd()
        os.chdir(tmp_path)

        try:
            # Create config file
            config_dir = tmp_path / ".egregora"
            config_dir.mkdir()
            config_file = config_dir / "config.yml"
            config_file.write_text("models:\n  writer: test")

            result = check_egregora_config()

            assert result.check == "Egregora Config"
            assert result.status == HealthStatus.OK
            assert "Valid config" in result.message
            assert result.details is not None
            assert "writer_model" in result.details
            assert "rag_enabled" in result.details

        finally:
            os.chdir(original_cwd)

    @patch("egregora.config.load_egregora_config")
    def test_invalid_config_file(self, mock_load_config: MagicMock, tmp_path: Path) -> None:
        """Returns ERROR when config file is invalid and can't be recovered."""
        # Mock config loading to raise an exception
        mock_load_config.side_effect = Exception("Invalid YAML structure")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)

        try:
            # Create config file (content doesn't matter since we're mocking)
            config_dir = tmp_path / ".egregora"
            config_dir.mkdir()
            config_file = config_dir / "config.yml"
            config_file.write_text("invalid: yaml: : content")

            result = check_egregora_config()

            assert result.check == "Egregora Config"
            assert result.status == HealthStatus.ERROR
            assert "Invalid config" in result.message

        finally:
            os.chdir(original_cwd)


class TestCheckAdapters:
    """Tests for check_adapters()."""

    def test_adapters_available(self) -> None:
        """Returns OK when adapters are registered."""
        result = check_adapters()

        assert result.check == "Source Adapters"
        assert result.status == HealthStatus.OK
        assert "adapters available" in result.message
        assert result.details is not None
        assert "adapters" in result.details

        # Should have at least whatsapp and slack
        adapters = result.details["adapters"]
        assert "whatsapp" in adapters
        assert "slack" in adapters

    @patch("egregora.ingestion.input_registry.list_sources")
    def test_no_adapters_registered(self, mock_list_sources: MagicMock) -> None:
        """Returns ERROR when no adapters are registered."""
        mock_list_sources.return_value = []

        result = check_adapters()

        assert result.status == HealthStatus.ERROR
        assert "No adapters registered" in result.message

    @patch("egregora.ingestion.input_registry.list_sources")
    def test_adapter_check_error(self, mock_list_sources: MagicMock) -> None:
        """Returns ERROR when adapter listing fails."""
        mock_list_sources.side_effect = Exception("Registry error")

        result = check_adapters()

        assert result.status == HealthStatus.ERROR
        assert "Failed to list adapters" in result.message


class TestRunDiagnostics:
    """Tests for run_diagnostics()."""

    def test_run_all_checks(self) -> None:
        """run_diagnostics() runs all checks and returns results."""
        results = run_diagnostics()

        # Should return 8 results (one per check)
        assert len(results) == 8

        # Check names should match
        check_names = [r.check for r in results]
        assert "Python Version" in check_names
        assert "Required Packages" in check_names
        assert "API Key" in check_names
        assert "DuckDB VSS Extension" in check_names
        assert "Git" in check_names
        assert "Cache Directory" in check_names
        assert "Egregora Config" in check_names
        assert "Source Adapters" in check_names

    def test_check_error_handling(self) -> None:
        """run_diagnostics() handles check failures gracefully."""
        # Patch one check to raise an exception
        with patch("egregora.diagnostics.check_python_version") as mock_check:
            mock_check.side_effect = Exception("Unexpected error")

            results = run_diagnostics()

            # Should still return all results
            assert len(results) == 8

            # First result should be an error
            python_result = results[0]
            assert python_result.status == HealthStatus.ERROR
            assert "Check failed" in python_result.message

    def test_all_checks_return_diagnostic_result(self) -> None:
        """All checks return DiagnosticResult instances."""
        results = run_diagnostics()

        for result in results:
            assert isinstance(result, DiagnosticResult)
            assert isinstance(result.status, HealthStatus)
            assert isinstance(result.check, str)
            assert isinstance(result.message, str)
            assert result.details is None or isinstance(result.details, dict)
