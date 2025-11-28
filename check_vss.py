import contextlib

import duckdb


def check_vss() -> None:
    conn = duckdb.connect(":memory:")

    try:
        conn.execute("INSTALL vss; LOAD vss;")
    except Exception:
        return

    result = conn.execute(
        "SELECT function_name FROM duckdb_functions() WHERE function_name LIKE 'vss_%'"
    ).fetchall()
    for _row in result:
        pass

    try:
        # Create dummy table
        conn.execute("CREATE TABLE items (id INT, embedding FLOAT[3])")
        conn.execute("INSERT INTO items VALUES (1, [1.0, 0.0, 0.0]), (2, [0.0, 1.0, 0.0])")

        # Try vss_match (if it exists)
        with contextlib.suppress(Exception):
            conn.execute("SELECT * FROM vss_match('items', 'embedding', [1.0, 0.0, 0.0]::FLOAT[3], 1)")

    except Exception:
        pass


if __name__ == "__main__":
    check_vss()
