from egregora.database.duckdb_manager import temp_storage


def test_ensure_sequence_default_injection():
    """Verify that SQL injection is PREVENTED in ensure_sequence_default.

    This test attempts to inject a DROP TABLE command via the sequence_name argument.
    The injection should fail to execute the DROP command, ensuring 'critical_data' remains.
    """
    with temp_storage() as storage:
        # 1. Create a sensitive table that the attacker wants to drop
        storage.execute_sql("CREATE TABLE critical_data (secret TEXT)")
        storage.execute_sql("INSERT INTO critical_data VALUES ('top_secret')")

        # 2. Create a table that we will modify with ensure_sequence_default
        storage.execute_sql("CREATE TABLE users (id INTEGER, name TEXT)")

        # Create a valid sequence so the first part of the injection works
        storage.execute_sql("CREATE SEQUENCE seq")

        # 3. Payload: closes the nextval(' call, executes DROP TABLE, comments out the rest
        # Original SQL: ... SET DEFAULT nextval('{sequence_name}')
        # Injection: seq'); DROP TABLE critical_data; --
        # Result: ... SET DEFAULT nextval('seq'); DROP TABLE critical_data; --')
        payload = "seq'); DROP TABLE critical_data; --"

        # 4. Attempt injection
        try:
            # We expect this might fail with a syntax error for the REST of the query
            # or succeed if the injection is perfect.
            # But the DROP TABLE should execute if it's vulnerable.
            storage.ensure_sequence_default("users", "id", payload)
        except Exception:  # noqa: S110
            # We don't care if the function raises an error (e.g. syntax error in the trailing part),
            # as long as the side effect (DROP TABLE) happened.
            pass

        # 5. Check if critical_data table is still there
        tables = storage.list_tables()

        # This assertion should FAIL if the code is vulnerable (Table is gone)
        # This matches the BDD "Red" step.
        assert "critical_data" in tables, (
            "VULNERABILITY CONFIRMED: critical_data table was dropped via SQL injection!"
        )


def test_ensure_sequence_default_happy_path_with_quotes():
    """Verify that valid sequence names with quotes are handled correctly (after fix)."""
    with temp_storage() as storage:
        storage.execute_sql("CREATE TABLE items (id INTEGER)")

        # A weird but valid sequence name
        weird_seq = "seq'with'quotes"
        storage.execute_sql(f'CREATE SEQUENCE "{weird_seq}"')

        storage.ensure_sequence_default("items", "id", weird_seq)

        # Verify the default was set correctly
        # The stored default should be: nextval('seq''with''quotes')
        row = storage.execute_query_single(
            "SELECT column_default FROM information_schema.columns WHERE table_name='items' AND column_name='id'"
        )
        assert row is not None
        # DuckDB might normalize the string, but it should contain the escaped quotes
        default_val = row[0]
        assert "nextval" in default_val
        assert (
            "seq''with''quotes" in default_val or 'seq"with"quotes' in default_val or weird_seq in default_val
        )
