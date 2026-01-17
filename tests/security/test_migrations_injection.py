
import duckdb
import pytest
from egregora.database.migrations import _get_existing_columns, _build_create_table_sql

def test_sql_injection_get_existing_columns():
    """Test that _get_existing_columns is vulnerable to SQL injection."""
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE valid_table (id INTEGER)")

    # Payload: trying to close the string and execute another command
    # PRAGMA table_info('valid_table'); CREATE TABLE pwned (id INTEGER); --')
    # If injection works, 'pwned' table will be created.

    payload = "valid_table'); CREATE TABLE pwned (id INTEGER); --"

    try:
        _get_existing_columns(conn, payload)
    except Exception:
        pass

    # Check if pwned table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]

    # If vulnerable, 'pwned' might exist.
    # Note: DuckDB execute might not support multiple statements in one call depending on driver.
    # But even syntax error shows injection is possible.

    # Let's try a simpler one: just breaking syntax to prove we left the string context.
    # PRAGMA table_info('valid_table' OR 1=1) --')

    # If we can break out of the quote, we have injection.

    # After fix, this should be treated as a table name lookup.
    # Since no table exists with that crazy name, it should raise CatalogException or similar,
    # BUT it should NOT raise ParserException (which implies syntax error due to injection).

    # We expect CatalogException because the table doesn't exist.
    with pytest.raises(duckdb.CatalogException) as excinfo:
         _get_existing_columns(conn, "valid_table') OR 1=1 --")

    # Verify the error message confirms it was looking for that exact table name
    assert "valid_table') OR 1=1 --" in str(excinfo.value)

def test_sql_injection_build_create_table():
    """Test that _build_create_table_sql is safe."""
    # This function returns a string, so we can check the string directly.
    payload = "valid_table; DROP TABLE documents; --"
    sql = _build_create_table_sql(payload)

    # It should be quoted now
    assert f'"{payload}"' in sql
