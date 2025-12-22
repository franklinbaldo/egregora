

import duckdb
from typer.testing import CliRunner

from egregora.cli.main import app

runner = CliRunner()

def test_db_migrate_command(tmp_path):
    """Test the 'db migrate' command."""
    # 1. Setup Site
    site_root = tmp_path / "test_site"
    site_root.mkdir()

    # Create legacy DB
    db_path = site_root / "pipeline.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE documents (
            id VARCHAR,
            title VARCHAR,
            updated TIMESTAMP,
            content VARCHAR,
            links JSON,
            authors JSON,
            contributors JSON,
            categories JSON
        )
    """)
    conn.close()

    # Create config pointing to this DB
    # We use absolute path to avoid ambiguity in test environment
    config_content = f"""
[database]
pipeline_db = "duckdb://{db_path}"
"""
    config_path = site_root / ".egregora.toml"
    config_path.write_text(config_content)

    # 2. Run Command
    result = runner.invoke(app, ["db", "migrate", str(site_root)])

    # 3. Verify Output
    assert result.exit_code == 0
    assert "Migration complete" in result.stdout

    # 4. Verify DB Schema
    conn = duckdb.connect(str(db_path))
    columns = [row[0] for row in conn.execute("DESCRIBE documents").fetchall()]
    conn.close()

    assert "doc_type" in columns
    assert "extensions" in columns
