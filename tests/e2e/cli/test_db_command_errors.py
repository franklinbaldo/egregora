from unittest.mock import patch

from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()


def test_db_migrate_invalid_config(tmp_path):
    site_root = tmp_path / "bad_site"
    site_root.mkdir()

    # Write invalid TOML
    (site_root / ".egregora.toml").write_text("invalid_toml [")

    result = runner.invoke(app, ["db", "migrate", str(site_root)])

    assert result.exit_code == 1
    assert "Failed to load configuration" in result.stdout


def test_db_migrate_migration_failure(tmp_path):
    site_root = tmp_path / "fail_site"
    site_root.mkdir()

    # Valid config
    (site_root / ".egregora.toml").write_text("")  # Empty uses default

    # Mock migrate_documents_table to raise exception
    with patch("egregora.cli.db.migrate_documents_table", side_effect=ValueError("Boom")):
        # Mock ibis.connect to avoid creating real DB
        with patch("egregora.cli.db.ibis.connect"):
            result = runner.invoke(app, ["db", "migrate", str(site_root)])

    assert result.exit_code == 1
    assert "Migration failed: Boom" in result.stdout


def test_db_migrate_no_db_configured(tmp_path):
    site_root = tmp_path / "no_db_site"
    site_root.mkdir()

    # Config with empty pipeline_db
    # We need to bypass validation? EgregoraConfig might enforce it?
    # EgregoraConfig.database.pipeline_db has a default.
    # If we set it to empty string?

    config_text = """
[database]
pipeline_db = ""
"""
    (site_root / ".egregora.toml").write_text(config_text)

    result = runner.invoke(app, ["db", "migrate", str(site_root)])

    assert result.exit_code == 1
    assert "No pipeline database configured" in result.stdout
