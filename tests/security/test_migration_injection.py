import logging

import duckdb
import pytest

from egregora.database.migrations import _get_existing_columns, _verify_all_constraints_present

logger = logging.getLogger(__name__)


def test_get_existing_columns_happy_path():
    """Test that _get_existing_columns works correctly for a valid table."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE valid_table (id INTEGER, name VARCHAR)")

    cols = _get_existing_columns(con, "valid_table")
    assert cols == {"id", "name"}


def test_get_existing_columns_sql_injection():
    """
    Test that _get_existing_columns is protected against SQL injection.
    We attempt to inject a DROP TABLE command.
    """
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE security_check (id INTEGER)")

    # Verify table exists
    result = con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='security_check'"
    ).fetchall()
    assert result[0][0] == 1, "Table should exist before test"

    # Injection payload: Closes single quote, executes DROP TABLE, comments out the rest
    malicious_table_name = "security_check'); DROP TABLE security_check; --"

    try:
        _get_existing_columns(con, malicious_table_name)
    except NameError:
        pytest.fail("NameError detected! Is quote_identifier imported?")
    except Exception as e:
        # We expect an exception (e.g. table not found or syntax error) because the name is invalid
        # But we MUST ensure the injected command didn't run.
        logger.debug(f"Expected exception caught during injection attempt: {e}")

    # Verify if table still exists
    result = con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='security_check'"
    ).fetchall()

    # If vulnerability exists, count will be 0. We assert it is 1.
    assert result[0][0] == 1, "SQL Injection succeeded! Table was dropped via _get_existing_columns."


def test_verify_constraints_sql_injection():
    """
    Test that _verify_all_constraints_present is protected against SQL injection.
    """
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE security_check_c (id INTEGER)")

    # Injection payload for WHERE clause
    malicious_table_name = "security_check_c' OR 1=1; DROP TABLE security_check_c; --"

    try:
        _verify_all_constraints_present(con, malicious_table_name)
    except NameError:
        pytest.fail("NameError detected!")
    except Exception as e:
        logger.debug(f"Expected exception caught during injection attempt: {e}")

    result = con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='security_check_c'"
    ).fetchall()
    assert result[0][0] == 1, (
        "SQL Injection succeeded! Table was dropped via _verify_all_constraints_present."
    )
