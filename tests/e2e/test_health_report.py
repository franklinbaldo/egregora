"""E2E test for Connection Health Report generation (RFC 041)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import duckdb

from egregora.output_sinks.mkdocs.scaffolding import MkDocsSiteScaffolder
from egregora.output_sinks.mkdocs.site_generator import SiteGenerator


def test_health_report_generation(tmp_path: Path):
    """Test that health report is generated correctly from pipeline database."""
    site_root = tmp_path / "test_site"
    scaffolder = MkDocsSiteScaffolder()
    scaffolder.scaffold(site_root, {"site_name": "Test Site"})

    # Setup directories
    docs_dir = site_root / "docs"
    posts_dir = docs_dir / "posts"
    profiles_dir = posts_dir / "profiles"
    media_dir = posts_dir / "media"
    journal_dir = docs_dir / "journal"

    # Create dummy profiles
    (profiles_dir / "alice-uuid").mkdir(parents=True, exist_ok=True)
    # Note: Health report logic (and SiteGenerator) ignores index.md and looks for other md files
    (profiles_dir / "alice-uuid" / "profile.md").write_text(
        "---\nname: Alice Wonderland\n---\n", encoding="utf-8"
    )

    # Setup pipeline database with staging_messages
    pipeline_db_path = site_root / "pipeline.duckdb"
    conn = duckdb.connect(str(pipeline_db_path))
    conn.execute("""
        CREATE TABLE staging_messages (
            event_id VARCHAR,
            tenant_id VARCHAR,
            source VARCHAR,
            thread_id VARCHAR,
            msg_id VARCHAR,
            ts TIMESTAMPTZ,
            author_raw VARCHAR,
            author_uuid VARCHAR,
            text VARCHAR,
            media_url VARCHAR,
            media_type VARCHAR,
            attrs JSON,
            pii_flags JSON,
            created_at TIMESTAMPTZ,
            created_by_run VARCHAR
        )
    """)

    now = datetime.now(UTC)

    # Insert messages for Alice (Hot, > 5 messages)
    for i in range(10):
        conn.execute(
            "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                f"evt-a-{i}",
                "t1",
                "whatsapp",
                "thread1",
                f"msg-a-{i}",
                now - timedelta(days=2),
                "Alice",
                "alice-uuid",
                f"Hello {i}",
                None,
                None,
                None,
                None,
                now,
                "run-1",
            ],
        )

    # Insert messages for Bob (Ghost, > 5 messages)
    for i in range(10):
        conn.execute(
            "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                f"evt-b-{i}",
                "t1",
                "whatsapp",
                "thread1",
                f"msg-b-{i}",
                now - timedelta(days=400),
                "Bob",
                "bob-uuid",
                f"Hi {i}",
                None,
                None,
                None,
                None,
                now,
                "run-1",
            ],
        )

    # Insert messages for Charlie (Few messages, should be filtered)
    for i in range(2):
        conn.execute(
            "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                f"evt-c-{i}",
                "t1",
                "whatsapp",
                "thread1",
                f"msg-c-{i}",
                now - timedelta(days=2),
                "Charlie",
                "charlie-uuid",
                f"Hey {i}",
                None,
                None,
                None,
                None,
                now,
                "run-1",
            ],
        )

    conn.close()

    # Initialize SiteGenerator
    # We can use MagicMock for UrlConvention/UrlContext as they are not used in health report
    generator = SiteGenerator(
        site_root=site_root,
        docs_dir=docs_dir,
        posts_dir=posts_dir,
        profiles_dir=profiles_dir,
        media_dir=media_dir,
        journal_dir=journal_dir,
        url_convention=MagicMock(),
        url_context=MagicMock(),
        pipeline_db_path=pipeline_db_path,
    )

    # Generate report
    generator.regenerate_health_report()

    # Verify output
    report_path = docs_dir / "health.md"
    assert report_path.exists(), "health.md should be generated"

    content = report_path.read_text(encoding="utf-8")

    # Check for presence of authors
    assert "Alice Wonderland" in content  # Resolved from profile
    assert "bob-uuid" in content or "Bob" in content  # Fallback or raw name

    # Check statuses
    assert "Hot" in content
    assert "Ghost" in content

    # Check that Charlie is excluded (min messages filter)
    assert "Charlie" not in content and "charlie-uuid" not in content

    # Check structure (headings)
    assert "Connection Health Report" in content
    assert "Ghost List" in content
