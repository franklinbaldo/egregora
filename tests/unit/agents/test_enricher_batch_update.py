from unittest.mock import MagicMock

import duckdb
import pytest

from egregora.agents.enricher import EnrichmentWorker


class TestEnricherBatchUpdate:
    @pytest.fixture
    def worker(self):
        ctx = MagicMock()
        ctx.storage = MagicMock()
        ctx.input_path = None  # Avoid zipfile logic
        ctx.config = MagicMock()

        # Patch BaseWorker init if needed, or just let it run (it usually just sets ctx)
        return EnrichmentWorker(ctx)

    def test_apply_media_replacements_batch_empty(self, worker):
        worker._apply_media_replacements_batch([])
        worker.ctx.storage.execute_sql.assert_not_called()

    def test_apply_media_replacements_batch_single(self, worker):
        replacements = [("old.jpg", "new.jpg")]
        worker._apply_media_replacements_batch(replacements)

        args = worker.ctx.storage.execute_sql.call_args
        query, params = args[0]

        assert "UPDATE messages SET text = replace(text, ?, ?) WHERE regexp_matches(text, ?)" in query
        assert params == ["old.jpg", "new.jpg", "old\\.jpg"]

    def test_apply_media_replacements_batch_multiple(self, worker):
        replacements = [("old1.jpg", "new1.jpg"), ("old2.png", "new2.png")]
        worker._apply_media_replacements_batch(replacements)

        args = worker.ctx.storage.execute_sql.call_args
        query, params = args[0]

        # Verify nested replace
        assert "replace(replace(text, ?, ?), ?, ?)" in query
        assert "WHERE regexp_matches(text, ?)" in query

        # Params: old1, new1, old2, new2, pattern
        assert params[:4] == ["old1.jpg", "new1.jpg", "old2.png", "new2.png"]
        # Pattern should match both, escaped
        assert params[4] == "old1\\.jpg|old2\\.png"

    def test_apply_media_replacements_batch_special_chars(self, worker):
        replacements = [("file(1).jpg", "file_1.jpg")]
        worker._apply_media_replacements_batch(replacements)

        args = worker.ctx.storage.execute_sql.call_args
        _, params = args[0]

        # Regex should escape parens
        assert params[2] == "file\\(1\\)\\.jpg"

    def test_apply_media_replacements_batch_integration(self):
        # Use real duckdb to verify SQL validity
        con = duckdb.connect(":memory:")
        con.execute("CREATE TABLE messages (text VARCHAR)")
        con.execute("INSERT INTO messages VALUES ('Hello old.jpg'), ('Hi file(1).jpg'), ('No match')")

        ctx = MagicMock()
        ctx.storage.execute_sql = lambda q, p: con.execute(q, p)
        ctx.input_path = None
        ctx.config = MagicMock()

        worker = EnrichmentWorker(ctx)

        replacements = [("old.jpg", "new.jpg"), ("file(1).jpg", "file_1.jpg")]

        worker._apply_media_replacements_batch(replacements)

        rows = con.execute("SELECT text FROM messages ORDER BY text").fetchall()
        assert rows[0][0] == "Hello new.jpg"
        assert rows[1][0] == "Hi file_1.jpg"
        assert rows[2][0] == "No match"
