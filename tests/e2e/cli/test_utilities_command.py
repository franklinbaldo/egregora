"""Integration tests for utility CLI commands (doctor, cache).

These tests verify that the doctor and cache management commands work correctly,
using CliRunner from typer.testing to simulate CLI invocations.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from egregora.cli.main import app

# Create a CLI runner for testing
runner = CliRunner()


class TestDoctorCommand:
    """Tests for 'egregora doctor' command."""

    def test_doctor_command_basic(self):
        """Test basic doctor command without flags."""
        result = runner.invoke(app, ["doctor"])

        # Doctor command should complete (may exit with 0 or 1 depending on environment)
        assert result.exit_code in (0, 1), f"Doctor failed unexpectedly: {result.stdout}"

        # Should contain diagnostic output
        assert "diagnostics" in result.stdout.lower() or "check" in result.stdout.lower()

    def test_doctor_command_verbose(self):
        """Test doctor command with --verbose flag."""
        result = runner.invoke(app, ["doctor", "--verbose"])

        assert result.exit_code in (0, 1)
        # Verbose output should contain more information
        assert "python" in result.stdout.lower() or "version" in result.stdout.lower()

    def test_doctor_command_verbose_short_flag(self):
        """Test doctor command with -v short flag."""
        result = runner.invoke(app, ["doctor", "-v"])

        assert result.exit_code in (0, 1)
        assert "python" in result.stdout.lower() or "version" in result.stdout.lower()

    def test_doctor_command_shows_summary(self):
        """Test that doctor command displays a summary."""
        result = runner.invoke(app, ["doctor"])

        # Should show summary with counts
        assert (
            "summary" in result.stdout.lower()
            or "ok" in result.stdout.lower()
            or "error" in result.stdout.lower()
        )

    def test_doctor_command_checks_python_version(self):
        """Test that doctor checks Python version."""
        result = runner.invoke(app, ["doctor"])

        assert "python" in result.stdout.lower()

    def test_doctor_command_checks_packages(self):
        """Test that doctor checks required packages."""
        result = runner.invoke(app, ["doctor"])

        # Should mention packages or dependencies
        output_lower = result.stdout.lower()
        assert (
            "package" in output_lower
            or "ibis" in output_lower
            or "duckdb" in output_lower
            or "error" in output_lower
        )

    def test_doctor_exit_code_on_success(self):
        """Test doctor exits with 0 when all checks pass (mocked)."""
        # This test mocks the diagnostics to all return OK
        with patch("egregora.diagnostics.run_diagnostics") as mock_diagnostics:
            from egregora.diagnostics import DiagnosticResult, HealthStatus

            mock_diagnostics.return_value = [
                DiagnosticResult(check="Python Version", status=HealthStatus.OK, message="Python 3.12.0"),
                DiagnosticResult(
                    check="Required Packages", status=HealthStatus.OK, message="All packages installed"
                ),
            ]

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 0

    def test_doctor_exit_code_on_error(self):
        """Test doctor exits with 1 when errors are found (mocked)."""
        with patch("egregora.diagnostics.run_diagnostics") as mock_diagnostics:
            from egregora.diagnostics import DiagnosticResult, HealthStatus

            mock_diagnostics.return_value = [
                DiagnosticResult(
                    check="API Key", status=HealthStatus.ERROR, message="GOOGLE_API_KEY not set"
                ),
            ]

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 1

    def test_doctor_continues_on_warnings(self):
        """Test doctor exits with 0 even when warnings are found."""
        with patch("egregora.diagnostics.run_diagnostics") as mock_diagnostics:
            from egregora.diagnostics import DiagnosticResult, HealthStatus

            mock_diagnostics.return_value = [
                DiagnosticResult(
                    check="DuckDB VSS", status=HealthStatus.WARNING, message="VSS extension not available"
                ),
            ]

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 0


@pytest.mark.skip(reason="cache command not implemented in current CLI")
class TestCacheStatsCommand:
    """Tests for 'egregora cache stats' command."""

    def test_cache_stats_empty_cache(self, tmp_path):
        """Test cache stats with empty cache directory."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])

        assert result.exit_code == 0
        assert "empty" in result.stdout.lower()

    def test_cache_stats_with_nonexistent_dir(self, tmp_path):
        """Test cache stats handles non-existent directory gracefully."""
        cache_dir = tmp_path / "nonexistent" / "checkpoints"

        result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])

        # Should not crash, should show 0 items or handle gracefully
        assert result.exit_code == 0 or "empty" in result.stdout.lower()

    def test_cache_stats_default_directory(self):
        """Test cache stats uses default directory."""
        result = runner.invoke(app, ["cache", "stats"])

        # Should complete without error (may be empty, but that's fine)
        assert result.exit_code == 0
        assert "cache" in result.stdout.lower() or "empty" in result.stdout.lower()

    def test_cache_stats_shows_size_info(self, tmp_path):
        """Test cache stats shows size information when cache exists."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create a mock stage directory with a checkpoint
        # Note: checkpoint module looks for 'checkpoint.pkl' files
        stage_dir = cache_dir / "enrichment" / "abc123"
        stage_dir.mkdir(parents=True)
        checkpoint_file = stage_dir / "checkpoint.pkl"
        checkpoint_file.write_bytes(b"test data" * 100)

        result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])

        assert result.exit_code == 0
        # Should show size information
        output_lower = result.stdout.lower()
        assert (
            "size" in output_lower
            or "mb" in output_lower
            or "kb" in output_lower
            or "enrichment" in output_lower
        )

    def test_cache_stats_shows_per_stage_breakdown(self, tmp_path):
        """Test cache stats shows per-stage breakdown."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create stage directories with proper checkpoint structure
        enrichment_dir = cache_dir / "enrichment" / "hash1"
        enrichment_dir.mkdir(parents=True)
        (enrichment_dir / "checkpoint.pkl").write_bytes(b"test" * 50)

        privacy_dir = cache_dir / "privacy" / "hash2"
        privacy_dir.mkdir(parents=True)
        (privacy_dir / "checkpoint.pkl").write_bytes(b"test" * 30)

        result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])

        assert result.exit_code == 0
        # Should mention stages or checkpoint counts
        output_lower = result.stdout.lower()
        assert (
            "stage" in output_lower
            or "enrichment" in output_lower
            or "privacy" in output_lower
            or "checkpoint" in output_lower
        )


@pytest.mark.skip(reason="cache command not implemented in current CLI")
class TestCacheClearCommand:
    """Tests for 'egregora cache clear' command."""

    def test_cache_clear_empty_cache(self, tmp_path):
        """Test cache clear with empty cache."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(app, ["cache", "clear", "--cache-dir", str(cache_dir), "--force"])

        assert result.exit_code == 0
        assert "empty" in result.stdout.lower()

    def test_cache_clear_with_force_flag(self, tmp_path):
        """Test cache clear with --force flag skips confirmation."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create checkpoints with proper directory structure
        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        (stage_dir / "checkpoint.pkl").write_bytes(b"test")

        stage_dir2 = cache_dir / "enrichment" / "hash2"
        stage_dir2.mkdir(parents=True)
        (stage_dir2 / "checkpoint.pkl").write_bytes(b"test")

        result = runner.invoke(app, ["cache", "clear", "--cache-dir", str(cache_dir), "--force"])

        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()
        # Checkpoints should be deleted
        assert len(list(cache_dir.rglob("checkpoint.pkl"))) == 0

    def test_cache_clear_with_short_force_flag(self, tmp_path):
        """Test cache clear with -f short flag."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        (stage_dir / "checkpoint.pkl").write_bytes(b"test")

        result = runner.invoke(app, ["cache", "clear", "--cache-dir", str(cache_dir), "-f"])

        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()

    def test_cache_clear_specific_stage(self, tmp_path):
        """Test cache clear for specific stage."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        enrichment_dir = cache_dir / "enrichment" / "hash1"
        enrichment_dir.mkdir(parents=True)
        (enrichment_dir / "checkpoint.pkl").write_bytes(b"test")

        privacy_dir = cache_dir / "privacy" / "hash2"
        privacy_dir.mkdir(parents=True)
        (privacy_dir / "checkpoint.pkl").write_bytes(b"test")

        result = runner.invoke(
            app, ["cache", "clear", "--cache-dir", str(cache_dir), "--stage", "enrichment", "--force"]
        )

        assert result.exit_code == 0
        # enrichment should be cleared
        assert len(list((cache_dir / "enrichment").rglob("checkpoint.pkl"))) == 0
        # privacy should remain
        assert len(list((cache_dir / "privacy").rglob("checkpoint.pkl"))) == 1

    def test_cache_clear_nonexistent_stage(self, tmp_path):
        """Test cache clear with non-existent stage."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(
            app, ["cache", "clear", "--cache-dir", str(cache_dir), "--stage", "nonexistent", "--force"]
        )

        # Should handle gracefully (may exit 0 or 1)
        assert result.exit_code in (0, 1)

    def test_cache_clear_cancels_without_force(self, tmp_path):
        """Test cache clear can be cancelled by user (without --force)."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        stage_dir = cache_dir / "enrichment"
        stage_dir.mkdir()
        checkpoint = stage_dir / "cp1.pkl"
        checkpoint.write_bytes(b"test")

        # Simulate user pressing 'n' at the confirmation prompt
        result = runner.invoke(
            app,
            ["cache", "clear", "--cache-dir", str(cache_dir)],
            input="n\n",  # Answer 'no' to confirmation
        )

        assert result.exit_code == 0
        # File should NOT be deleted
        assert checkpoint.exists()


@pytest.mark.skip(reason="cache command not implemented in current CLI")
class TestCacheGcCommand:
    """Tests for 'egregora cache gc' (garbage collection) command."""

    def test_cache_gc_requires_argument(self, tmp_path):
        """Test cache gc requires either --keep-last or --max-size."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir)])

        assert result.exit_code == 1
        assert "must specify" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_cache_gc_with_keep_last(self, tmp_path):
        """Test cache gc with --keep-last flag."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create multiple checkpoints with proper structure
        stage_dir = cache_dir / "enrichment"
        stage_dir.mkdir()
        for i in range(5):
            hash_dir = stage_dir / f"hash{i}"
            hash_dir.mkdir()
            (hash_dir / "checkpoint.pkl").write_bytes(b"test" * (i + 1))

        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir), "--keep-last", "2"])

        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()

    def test_cache_gc_keep_last_with_stage(self, tmp_path):
        """Test cache gc keeps last N for specific stage."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create multiple stages with proper structure
        for stage in ["enrichment", "privacy"]:
            stage_dir = cache_dir / stage
            stage_dir.mkdir()
            for i in range(3):
                hash_dir = stage_dir / f"hash{i}"
                hash_dir.mkdir()
                (hash_dir / "checkpoint.pkl").write_bytes(b"test")

        result = runner.invoke(
            app, ["cache", "gc", "--cache-dir", str(cache_dir), "--keep-last", "1", "--stage", "enrichment"]
        )

        assert result.exit_code == 0

    def test_cache_gc_with_max_size_gb(self, tmp_path):
        """Test cache gc with --max-size in GB."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create mock checkpoint that's "large"
        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        # Create a large-ish file (1 MB)
        (stage_dir / "checkpoint.pkl").write_bytes(b"x" * (1024 * 1024))

        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir), "--max-size", "1GB"])

        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower() or "0" in result.stdout

    def test_cache_gc_with_max_size_mb(self, tmp_path):
        """Test cache gc with --max-size in MB."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        (stage_dir / "checkpoint.pkl").write_bytes(b"x" * (512 * 1024))  # 512 KB

        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir), "--max-size", "1MB"])

        assert result.exit_code == 0

    def test_cache_gc_rejects_both_flags(self, tmp_path):
        """Test cache gc rejects both --keep-last and --max-size together."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(
            app, ["cache", "gc", "--cache-dir", str(cache_dir), "--keep-last", "5", "--max-size", "10GB"]
        )

        assert result.exit_code == 1
        assert "cannot use both" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_cache_gc_invalid_size_format(self, tmp_path):
        """Test cache gc handles invalid size format."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(
            app, ["cache", "gc", "--cache-dir", str(cache_dir), "--max-size", "invalid_size"]
        )

        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_cache_gc_with_max_size_kb(self, tmp_path):
        """Test cache gc with --max-size in KB."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        (stage_dir / "checkpoint.pkl").write_bytes(b"test" * 100)

        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir), "--max-size", "10KB"])

        assert result.exit_code == 0

    def test_cache_gc_empty_cache_with_keep_last(self, tmp_path):
        """Test cache gc on empty cache with --keep-last."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir), "--keep-last", "5"])

        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower() or "0" in result.stdout


@pytest.mark.skip(reason="cache command not implemented in current CLI")
class TestCacheCommandsIntegration:
    """Integration tests combining multiple cache commands."""

    def test_cache_workflow_stats_then_clear(self, tmp_path):
        """Test typical cache workflow: check stats, then clear."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create cache with proper checkpoint structure
        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        (stage_dir / "checkpoint.pkl").write_bytes(b"test" * 50)

        # Check stats
        stats_result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])
        assert stats_result.exit_code == 0
        assert (
            "enrichment" in stats_result.stdout.lower()
            or "checkpoint" in stats_result.stdout.lower()
            or "size" in stats_result.stdout.lower()
        )

        # Clear cache
        clear_result = runner.invoke(app, ["cache", "clear", "--cache-dir", str(cache_dir), "--force"])
        assert clear_result.exit_code == 0

        # Verify empty
        final_stats = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])
        assert final_stats.exit_code == 0
        assert "empty" in final_stats.stdout.lower() or "0" in final_stats.stdout

    def test_cache_workflow_gc_then_stats(self, tmp_path):
        """Test cache workflow: garbage collect, then check stats."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Create cache with multiple entries and proper structure
        for stage in ["enrichment", "privacy"]:
            stage_dir = cache_dir / stage
            stage_dir.mkdir()
            for i in range(3):
                hash_dir = stage_dir / f"hash{i}"
                hash_dir.mkdir()
                (hash_dir / "checkpoint.pkl").write_bytes(b"test")

        # Run GC
        gc_result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir), "--keep-last", "1"])
        assert gc_result.exit_code == 0

        # Check final stats
        stats_result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])
        assert stats_result.exit_code == 0


@pytest.mark.skip(reason="cache command not implemented in current CLI")
class TestCacheDefaultDirectory:
    """Tests for default cache directory behavior."""

    def test_cache_stats_with_default_directory(self):
        """Test cache stats works with default directory (even if it doesn't exist)."""
        result = runner.invoke(app, ["cache", "stats"])

        # Should complete without crashing
        assert result.exit_code == 0
        assert "cache" in result.stdout.lower() or "empty" in result.stdout.lower()

    def test_cache_clear_with_default_directory(self):
        """Test cache clear can use default directory."""
        result = runner.invoke(app, ["cache", "clear", "--force"])

        # Should complete (cache may be empty, which is fine)
        assert result.exit_code == 0

    def test_cache_gc_with_default_directory(self):
        """Test cache gc can use default directory."""
        result = runner.invoke(app, ["cache", "gc", "--keep-last", "5"])

        # Should complete (may delete nothing if cache empty)
        assert result.exit_code == 0


@pytest.mark.skip(reason="cache command not implemented in current CLI")
class TestDoctorAndCacheOutputFormat:
    """Tests for output formatting and readability."""

    def test_doctor_output_is_readable(self):
        """Test doctor command produces readable output."""
        result = runner.invoke(app, ["doctor"])

        assert result.exit_code in (0, 1)
        # Output should not be empty
        assert len(result.stdout) > 0
        # Should contain some check results
        output_lines = [l for l in result.stdout.split("\n") if l.strip()]
        assert len(output_lines) > 0

    def test_cache_stats_output_is_readable(self, tmp_path):
        """Test cache stats produces readable output."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        stage_dir = cache_dir / "enrichment" / "hash1"
        stage_dir.mkdir(parents=True)
        (stage_dir / "checkpoint.pkl").write_bytes(b"x" * 1000)

        result = runner.invoke(app, ["cache", "stats", "--cache-dir", str(cache_dir)])

        assert result.exit_code == 0
        # Should contain readable size information
        output = result.stdout.lower()
        assert "size" in output or "cache" in output or "enrichment" in output

    def test_cache_commands_error_messages_are_helpful(self, tmp_path):
        """Test cache commands provide helpful error messages."""
        cache_dir = tmp_path / "checkpoints"
        cache_dir.mkdir(parents=True)

        # Test missing arguments
        result = runner.invoke(app, ["cache", "gc", "--cache-dir", str(cache_dir)])

        assert result.exit_code == 1
        # Error message should be helpful
        output = result.stdout.lower()
        assert "must specify" in output or "error" in output or "keep-last" in output or "max-size" in output
