"""Tests for Connection Health Report (RFC 041)."""

from datetime import UTC, datetime, timedelta

import pytest

from egregora.orchestration.pipelines.health import (
    AuthorHealth,
    _classify_status,
    compute_summary_stats,
    get_connection_health_data,
)


class TestClassifyStatus:
    """Test connection status classification by silence duration."""

    def test_hot_within_7_days(self):
        assert _classify_status(0) == "Hot"
        assert _classify_status(3) == "Hot"
        assert _classify_status(7) == "Hot"

    def test_warm_8_to_30_days(self):
        assert _classify_status(8) == "Warm"
        assert _classify_status(15) == "Warm"
        assert _classify_status(30) == "Warm"

    def test_cool_31_to_90_days(self):
        assert _classify_status(31) == "Cool"
        assert _classify_status(60) == "Cool"
        assert _classify_status(90) == "Cool"

    def test_cold_91_to_180_days(self):
        assert _classify_status(91) == "Cold"
        assert _classify_status(120) == "Cold"
        assert _classify_status(180) == "Cold"

    def test_frozen_181_to_365_days(self):
        assert _classify_status(181) == "Frozen"
        assert _classify_status(300) == "Frozen"
        assert _classify_status(365) == "Frozen"

    def test_ghost_over_365_days(self):
        assert _classify_status(366) == "Ghost"
        assert _classify_status(730) == "Ghost"
        assert _classify_status(1000) == "Ghost"


class TestAuthorHealth:
    """Test AuthorHealth dataclass properties."""

    def _make_entry(
        self,
        *,
        first_seen_days_ago: int = 365,
        last_seen_days_ago: int = 30,
        msg_count: int = 100,
    ) -> AuthorHealth:
        now = datetime.now(UTC)
        return AuthorHealth(
            author_uuid="test-uuid",
            author_name="Alice",
            first_seen=now - timedelta(days=first_seen_days_ago),
            last_seen=now - timedelta(days=last_seen_days_ago),
            msg_count=msg_count,
            days_since_last=last_seen_days_ago,
            status=_classify_status(last_seen_days_ago),
        )

    def test_years_active(self):
        entry = self._make_entry(first_seen_days_ago=730, last_seen_days_ago=0)
        assert 1.9 <= entry.years_active <= 2.1

    def test_years_active_same_day(self):
        entry = self._make_entry(first_seen_days_ago=0, last_seen_days_ago=0)
        assert entry.years_active == 0.0

    def test_messages_per_year(self):
        entry = self._make_entry(
            first_seen_days_ago=365,
            last_seen_days_ago=0,
            msg_count=100,
        )
        assert 95 <= entry.messages_per_year <= 105

    def test_messages_per_year_zero_duration(self):
        entry = self._make_entry(
            first_seen_days_ago=0,
            last_seen_days_ago=0,
            msg_count=50,
        )
        assert entry.messages_per_year == 50.0

    def test_status_classification(self):
        hot = self._make_entry(last_seen_days_ago=3)
        assert hot.status == "Hot"

        ghost = self._make_entry(last_seen_days_ago=400)
        assert ghost.status == "Ghost"

    def test_frozen_dataclass(self):
        entry = self._make_entry()
        with pytest.raises(AttributeError):
            entry.author_name = "Bob"


class TestComputeSummaryStats:
    """Test summary statistics computation."""

    def test_empty_list(self):
        stats = compute_summary_stats([])
        assert stats["total_contacts"] == 0
        assert stats["status_counts"] == {}
        assert stats["avg_silence_days"] == 0
        assert stats["total_messages"] == 0

    def test_single_entry(self):
        now = datetime.now(UTC)
        entry = AuthorHealth(
            author_uuid="uuid-1",
            author_name="Alice",
            first_seen=now - timedelta(days=100),
            last_seen=now - timedelta(days=10),
            msg_count=50,
            days_since_last=10,
            status="Warm",
        )
        stats = compute_summary_stats([entry])
        assert stats["total_contacts"] == 1
        assert stats["status_counts"] == {"Warm": 1}
        assert stats["avg_silence_days"] == 10
        assert stats["total_messages"] == 50

    def test_multiple_entries(self):
        now = datetime.now(UTC)
        entries = [
            AuthorHealth(
                author_uuid="uuid-1",
                author_name="Alice",
                first_seen=now - timedelta(days=100),
                last_seen=now - timedelta(days=5),
                msg_count=50,
                days_since_last=5,
                status="Hot",
            ),
            AuthorHealth(
                author_uuid="uuid-2",
                author_name="Bob",
                first_seen=now - timedelta(days=200),
                last_seen=now - timedelta(days=400),
                msg_count=30,
                days_since_last=400,
                status="Ghost",
            ),
        ]
        stats = compute_summary_stats(entries)
        assert stats["total_contacts"] == 2
        assert stats["status_counts"] == {"Hot": 1, "Ghost": 1}
        assert stats["avg_silence_days"] == 202  # (5 + 400) / 2 rounded
        assert stats["total_messages"] == 80


class TestGetConnectionHealthData:
    """Test database query for connection health data."""

    def test_nonexistent_db_returns_empty(self, tmp_path):
        result = get_connection_health_data(
            pipeline_db_path=tmp_path / "nonexistent.duckdb",
        )
        assert result == []

    def test_none_db_path_returns_empty(self):
        result = get_connection_health_data(pipeline_db_path=None)
        assert result == []

    def test_query_with_real_duckdb(self, tmp_path):
        """Test with an actual DuckDB staging_messages table."""
        import duckdb

        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))

        # Create staging_messages table matching the schema
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
        # Alice: 10 messages, last seen 5 days ago
        for i in range(10):
            conn.execute(
                "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    f"evt-a-{i}",
                    "t1",
                    "whatsapp",
                    "thread1",
                    f"msg-a-{i}",
                    now - timedelta(days=5 + i),
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

        # Bob: 8 messages, last seen 200 days ago
        for i in range(8):
            conn.execute(
                "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    f"evt-b-{i}",
                    "t1",
                    "whatsapp",
                    "thread1",
                    f"msg-b-{i}",
                    now - timedelta(days=200 + i),
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

        # Charlie: 2 messages (below min_messages threshold of 5)
        for i in range(2):
            conn.execute(
                "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    f"evt-c-{i}",
                    "t1",
                    "whatsapp",
                    "thread1",
                    f"msg-c-{i}",
                    now - timedelta(days=50 + i),
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

        result = get_connection_health_data(
            pipeline_db_path=db_path,
            now=now,
        )

        # Charlie should be excluded (only 2 messages, min is 5)
        assert len(result) == 2

        # Sorted by days_since_last descending (ghosts first)
        assert result[0].author_uuid == "bob-uuid"
        assert result[1].author_uuid == "alice-uuid"

        # Check Bob (Cold/Frozen range)
        assert result[0].msg_count == 8
        assert result[0].days_since_last >= 200

        # Check Alice (Hot)
        assert result[1].msg_count == 10
        assert result[1].status == "Hot"

    def test_min_messages_filter(self, tmp_path):
        """Test that min_messages parameter filters correctly."""
        import duckdb

        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE staging_messages (
                event_id VARCHAR, tenant_id VARCHAR, source VARCHAR,
                thread_id VARCHAR, msg_id VARCHAR, ts TIMESTAMPTZ,
                author_raw VARCHAR, author_uuid VARCHAR, text VARCHAR,
                media_url VARCHAR, media_type VARCHAR, attrs JSON,
                pii_flags JSON, created_at TIMESTAMPTZ, created_by_run VARCHAR
            )
        """)

        now = datetime.now(UTC)
        for i in range(3):
            conn.execute(
                "INSERT INTO staging_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    f"evt-{i}",
                    "t1",
                    "whatsapp",
                    "thread1",
                    f"msg-{i}",
                    now - timedelta(days=i),
                    "Dave",
                    "dave-uuid",
                    f"Msg {i}",
                    None,
                    None,
                    None,
                    None,
                    now,
                    "run-1",
                ],
            )
        conn.close()

        # With min_messages=5 (default), Dave should be excluded
        result = get_connection_health_data(pipeline_db_path=db_path, now=now)
        assert len(result) == 0

        # With min_messages=2, Dave should be included
        result = get_connection_health_data(pipeline_db_path=db_path, min_messages=2, now=now)
        assert len(result) == 1
        assert result[0].author_uuid == "dave-uuid"
