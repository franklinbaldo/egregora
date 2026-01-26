from egregora.database.duckdb_manager import DuckDBStorageManager


def test_execute_wrappers_use_default_params(tmp_path):
    manager = DuckDBStorageManager(tmp_path / "execute.duckdb")

    class SpyProxy:
        def __init__(self, conn):
            self.conn = conn
            self.calls: list = []

        def execute(self, sql: str, params=None):  # type: ignore[override]
            self.calls.append(params)
            return self.conn.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self.conn, name)

    manager._conn = SpyProxy(manager._conn)

    manager.execute_sql("SELECT ?", params=[1])
    assert manager._conn.calls[-1] == [1]

    manager.close()
