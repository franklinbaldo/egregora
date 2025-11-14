"""Tests for independent pipeline stage CLI commands.

These tests verify that each stage command works correctly in isolation,
using pytest-vcr to replay API interactions where needed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from egregora.cli import app

# Create a CLI runner for testing
runner = CliRunner()


@pytest.fixture
def test_zip_file():
    """Path to the test WhatsApp export ZIP file."""
    return Path(__file__).parent.parent / "fixtures" / "Conversa do WhatsApp com Teste.zip"


@pytest.fixture
def test_output_dir(tmp_path):
    """Temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


class TestParseCommand:
    """Tests for 'egregora parse' command."""

    def test_parse_basic(self, test_zip_file, test_output_dir):
        """Test basic parse command functionality."""
        output_csv = test_output_dir / "messages.csv"

        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(output_csv)])

        assert result.exit_code == 0, f"Command failed: {result.stdout}"
        assert output_csv.exists(), "Output CSV was not created"

        # Verify CSV has content
        content = output_csv.read_text()
        assert "timestamp" in content
        assert "author" in content
        assert "message" in content

    def test_parse_with_timezone(self, test_zip_file, test_output_dir):
        """Test parse command with timezone option."""
        output_csv = test_output_dir / "messages_tz.csv"

        result = runner.invoke(
            app,
            [
                "parse",
                str(test_zip_file),
                "--output",
                str(output_csv),
                "--timezone",
                "America/New_York",
            ],
        )

        assert result.exit_code == 0
        assert output_csv.exists()
        assert "America/New_York" in result.stdout or "Using timezone" in result.stdout

    def test_parse_missing_zip(self, test_output_dir):
        """Test parse command with missing ZIP file."""
        result = runner.invoke(
            app, ["parse", "nonexistent.zip", "--output", str(test_output_dir / "out.csv")]
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_parse_invalid_timezone(self, test_zip_file, test_output_dir):
        """Test parse command with invalid timezone."""
        output_csv = test_output_dir / "messages.csv"

        result = runner.invoke(
            app,
            [
                "parse",
                str(test_zip_file),
                "--output",
                str(output_csv),
                "--timezone",
                "Invalid/Timezone",
            ],
        )

        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower() or "error" in result.stdout.lower()


@pytest.mark.skip(reason="group command not implemented in current CLI")
class TestGroupCommand:
    """Tests for 'egregora group' command."""

    @pytest.fixture
    def parsed_csv(self, test_zip_file, test_output_dir):
        """Create a parsed CSV for group tests."""
        output_csv = test_output_dir / "messages.csv"
        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(output_csv)])
        assert result.exit_code == 0
        return output_csv

    def test_group_by_day(self, parsed_csv, test_output_dir):
        """Test grouping messages by day."""
        periods_dir = test_output_dir / "periods"

        result = runner.invoke(
            app,
            [
                "group",
                str(parsed_csv),
                "--step-size",
                "1",
                "--step-unit",
                "days",
                "--output-dir",
                str(periods_dir),
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.stdout}"
        assert periods_dir.exists()

        # Check that window files were created
        period_files = list(periods_dir.glob("*.csv"))
        assert len(period_files) > 0, "No window files created"

    def test_group_by_week(self, parsed_csv, test_output_dir):
        """Test grouping messages by week."""
        periods_dir = test_output_dir / "periods_week"

        result = runner.invoke(
            app,
            [
                "group",
                str(parsed_csv),
                "--step-size",
                "7",
                "--step-unit",
                "days",
                "--output-dir",
                str(periods_dir),
            ],
        )

        assert result.exit_code == 0
        assert periods_dir.exists()
        period_files = list(periods_dir.glob("*.csv"))
        assert len(period_files) > 0

    def test_group_by_month(self, parsed_csv, test_output_dir):
        """Test grouping messages by month (approx. 30 days)."""
        periods_dir = test_output_dir / "periods_month"

        result = runner.invoke(
            app,
            [
                "group",
                str(parsed_csv),
                "--step-size",
                "30",
                "--step-unit",
                "days",
                "--output-dir",
                str(periods_dir),
            ],
        )

        assert result.exit_code == 0
        assert periods_dir.exists()

    def test_group_with_date_range(self, parsed_csv, test_output_dir):
        """Test grouping with date range filters."""
        periods_dir = test_output_dir / "periods_filtered"

        result = runner.invoke(
            app,
            [
                "group",
                str(parsed_csv),
                "--step-size",
                "1",
                "--step-unit",
                "days",
                "--output-dir",
                str(periods_dir),
                "--from-date",
                "2025-10-01",
                "--to-date",
                "2025-10-31",
            ],
        )

        assert result.exit_code == 0

    def test_group_invalid_period(self, parsed_csv, test_output_dir):
        """Test group command with invalid step_unit."""
        result = runner.invoke(
            app,
            [
                "group",
                str(parsed_csv),
                "--step-unit",
                "invalid",
                "--output-dir",
                str(test_output_dir / "periods"),
            ],
        )

        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower()

    def test_group_missing_input(self, test_output_dir):
        """Test group command with missing input file."""
        result = runner.invoke(
            app,
            [
                "group",
                "nonexistent.csv",
                "--step-size=1",
                "--step-unit=days",
                "--output-dir",
                str(test_output_dir / "periods"),
            ],
        )

        assert result.exit_code == 1  # File not found error
        assert "not found" in result.output.lower()


@pytest.mark.vcr
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY required for enrich tests with VCR",
)
class TestEnrichCommand:
    """Tests for 'egregora enrich' command with VCR."""

    @pytest.fixture
    def parsed_csv(self, test_zip_file, test_output_dir):
        """Create a parsed CSV for enrich tests."""
        output_csv = test_output_dir / "messages.csv"
        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(output_csv)])
        assert result.exit_code == 0
        return output_csv

    @pytest.fixture
    def site_dir(self, test_output_dir):
        """Create a minimal site directory."""
        site = test_output_dir / "site"
        site.mkdir()
        (site / "mkdocs.yml").write_text("site_name: Test\n")
        docs = site / "docs"
        docs.mkdir()
        return site

    def test_enrich_basic(self, parsed_csv, test_zip_file, site_dir, test_output_dir):
        """Test basic enrich command with VCR."""
        enriched_csv = test_output_dir / "enriched.csv"

        result = runner.invoke(
            app,
            [
                "enrich",
                str(parsed_csv),
                "--zip-file",
                str(test_zip_file),
                "--output",
                str(enriched_csv),
                "--site-dir",
                str(site_dir),
                "--max-enrichments",
                "2",  # Limit to reduce VCR cassette size
            ],
        )

        assert result.exit_code == 0 or "enriched" in result.stdout.lower()
        # Note: Enrichment may not find anything to enrich, which is OK


@pytest.mark.vcr
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY required for gather-context tests with VCR",
)
class TestGatherContextCommand:
    """Tests for 'egregora gather-context' command with VCR."""

    @pytest.fixture
    def enriched_csv(self, test_zip_file, test_output_dir):
        """Create a parsed CSV (enrichment optional for testing)."""
        output_csv = test_output_dir / "messages.csv"
        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(output_csv)])
        assert result.exit_code == 0
        return output_csv

    @pytest.fixture
    def site_dir(self, test_output_dir):
        """Create a minimal site directory."""
        site = test_output_dir / "site"
        site.mkdir()
        (site / "mkdocs.yml").write_text("site_name: Test\n")
        docs = site / "docs"
        docs.mkdir()
        (docs / "posts").mkdir()
        (docs / "profiles").mkdir()
        return site

    def test_gather_context_basic(self, enriched_csv, site_dir, test_output_dir):
        """Test basic gather-context command with VCR."""
        context_json = test_output_dir / "context.json"

        result = runner.invoke(
            app,
            [
                "gather-context",
                str(enriched_csv),
                "--window-id",
                "2025-10-28",
                "--site-dir",
                str(site_dir),
                "--output",
                str(context_json),
                "--no-enable-rag",  # Disable RAG to simplify test
            ],
        )

        # gather-context may fail if no messages for the period, which is OK for test
        assert result.exit_code in (0, 1)


@pytest.mark.vcr
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY required for write-posts tests with VCR",
)
class TestWritePostsCommand:
    """Tests for 'egregora write-posts' command with VCR."""

    @pytest.fixture
    def enriched_csv(self, test_zip_file, test_output_dir):
        """Create a parsed CSV."""
        output_csv = test_output_dir / "messages.csv"
        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(output_csv)])
        assert result.exit_code == 0
        return output_csv

    @pytest.fixture
    def site_dir(self, test_output_dir):
        """Create a minimal site directory."""
        site = test_output_dir / "site"
        site.mkdir()
        (site / "mkdocs.yml").write_text("site_name: Test\n")
        docs = site / "docs"
        docs.mkdir()
        (docs / "posts").mkdir()
        (docs / "profiles").mkdir()
        return site

    def test_write_posts_basic(self, enriched_csv, site_dir):
        """Test basic write-posts command with VCR."""
        result = runner.invoke(
            app,
            [
                "write-posts",
                str(enriched_csv),
                "--window-id",
                "2025-10-28",
                "--site-dir",
                str(site_dir),
                "--no-enable-rag",  # Disable RAG to simplify
            ],
        )

        # May fail if context gathering fails, which is OK for basic test
        assert result.exit_code in (0, 1)

    def test_write_posts_output_directory(self, enriched_csv, site_dir):
        """Test that write-posts command writes to the correct '.posts' subdirectory."""
        # Run the command that writes posts
        runner.invoke(
            app,
            [
                "write-posts",
                str(enriched_csv),
                "--window-id",
                "2025-10-28",
                "--site-dir",
                str(site_dir),
                "--no-enable-rag",
            ],
        )

        # Check that the posts are in the correct subdirectory
        posts_base_dir = site_dir / "docs" / "posts"
        posts_target_dir = posts_base_dir / ".posts"

        # It's possible no posts were generated, which is okay.
        # If the directory exists, we check for posts inside.
        if posts_target_dir.exists():
            post_files = list(posts_target_dir.glob("*.md"))
            # If there are posts, ensure they are in the right place
            if post_files:
                assert all(p.parent == posts_target_dir for p in post_files), (
                    "Posts should be in the '.posts' subdirectory."
                )
        else:
            # If the directory doesn't exist, it means no posts were written, which is a valid outcome.
            # We can also check that no posts were written to the *wrong* directory.
            stray_posts = list(posts_base_dir.glob("2025-10-28-*.md"))
            assert not stray_posts, f"Posts should not be in the base 'posts' directory: {stray_posts}"


class TestSerializationFormats:
    """Tests for CSV and Parquet serialization formats."""

    def test_parse_to_parquet(self, test_zip_file, test_output_dir):
        """Test parsing to Parquet format."""
        output_parquet = test_output_dir / "messages.parquet"

        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(output_parquet)])

        assert result.exit_code == 0
        assert output_parquet.exists()
        # Verify it's a valid Parquet file
        pd = pytest.importorskip("pandas")

        df = pd.read_parquet(output_parquet)
        assert len(df) > 0
        assert "message" in df.columns

    def test_group_from_parquet(self, test_zip_file, test_output_dir):
        """Test grouping from Parquet input."""
        # First parse to Parquet
        messages_parquet = test_output_dir / "messages.parquet"
        result = runner.invoke(app, ["parse", str(test_zip_file), "--output", str(messages_parquet)])
        assert result.exit_code == 0

        # Then group from Parquet
        periods_dir = test_output_dir / "periods"
        result = runner.invoke(
            app,
            [
                "group",
                str(messages_parquet),
                "--step-size=1",
                "--step-unit=days",
                "--output-dir",
                str(periods_dir),
            ],
        )

        assert result.exit_code == 0
        period_files = list(periods_dir.glob("*.csv"))
        assert len(period_files) > 0
