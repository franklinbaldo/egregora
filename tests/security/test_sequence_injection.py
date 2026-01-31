"""Security tests for SQL injection in sequence operations."""

import duckdb
import pytest
from egregora.database.duckdb_manager import DuckDBStorageManager, temp_storage

def test_ensure_sequence_default_injection():
    """Test that SQL injection via sequence name in ensure_sequence_default is prevented."""
    with temp_storage() as storage:
        # Create a table to target for dropping
        storage.execute_sql("CREATE TABLE target_table (id INTEGER)")
        storage.execute_sql("INSERT INTO target_table VALUES (1)")

        # Create a table to alter
        storage.execute_sql("CREATE TABLE vulnerable_table (id INTEGER, val INTEGER)")

        # Create a valid sequence 'seq' so the first part of injection succeeds
        storage.ensure_sequence("seq")

        # Malicious sequence name that attempts to close the quote and execute DROP TABLE
        # The resulting SQL would look like:
        # ALTER TABLE "vulnerable_table" ALTER COLUMN "id" SET DEFAULT nextval('seq'); DROP TABLE target_table; --')
        malicious_sequence = "seq'); DROP TABLE target_table; --"

        # Create the malicious sequence itself using safe method
        # If the fix works, it should use THIS sequence, not the injected SQL.
        storage.ensure_sequence(malicious_sequence)

        # Attempt the injection
        # If vulnerable, this will execute DROP TABLE target_table
        # If fixed, this will set default to nextval('seq''); DROP TABLE target_table; --')
        try:
            storage.ensure_sequence_default("vulnerable_table", "id", malicious_sequence)
        except Exception as e:
            # If it fails for some other reason (like syntax error in fixed version), that's fine for now,
            # as long as it's not executing the injection.
            # But ideally it should succeed and set the default to the weird sequence.
            print(f"ensure_sequence_default raised: {e}")

        # Verify target_table still exists
        assert storage.table_exists("target_table"), "SQL Injection successful! target_table was dropped."

def test_next_sequence_values_injection():
    """Test that SQL injection via sequence name in next_sequence_values is prevented."""
    with temp_storage() as storage:
        # Create a target table
        storage.execute_sql("CREATE TABLE target_table (id INTEGER)")

        # Malicious sequence name
        # next_sequence_values does: SELECT nextval('{sequence_name}')
        # Injection: seq'); DROP TABLE target_table; --
        malicious_sequence = "seq'); DROP TABLE target_table; --"

        # Note: We can't easily create a sequence with this name to make nextval succeed if injection fails
        # but execution succeeds.
        # However, if injection works, it will execute the second statement.

        # We expect a SequenceFetchError or duckdb.Error because the sequence likely doesn't exist
        # But we must ensure target_table is NOT dropped.

        try:
            storage.next_sequence_values(malicious_sequence)
        except Exception:
            # We expect an error because the sequence probably doesn't exist
            pass

        assert storage.table_exists("target_table"), "SQL Injection successful! target_table was dropped."

def test_next_sequence_values_happy_path():
    """Verify that next_sequence_values works correctly for normal sequences."""
    with temp_storage() as storage:
        storage.ensure_sequence("test_seq", start=10)

        val = storage.next_sequence_value("test_seq")
        assert val == 10

        vals = storage.next_sequence_values("test_seq", count=2)
        assert vals == [11, 12]

def test_next_sequence_values_special_chars():
    """Verify that next_sequence_values handles legitimate special characters correctly."""
    with temp_storage() as storage:
        # A sequence name with a quote in it (valid identifier)
        weird_name = "seq'with_quote"
        storage.ensure_sequence(weird_name, start=1)

        val = storage.next_sequence_value(weird_name)
        assert val == 1
