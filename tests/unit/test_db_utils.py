
from egregora.database.utils import resolve_db_uri


def test_resolve_db_uri_relative(tmp_path):
    site_root = tmp_path / "site"
    site_root.mkdir()

    uri = "duckdb:///./pipeline.duckdb"
    resolved = resolve_db_uri(uri, site_root)

    expected = f"duckdb://{site_root.resolve() / 'pipeline.duckdb'}"
    assert resolved == expected

def test_resolve_db_uri_absolute(tmp_path):
    site_root = tmp_path / "site"
    site_root.mkdir()

    abs_path = (tmp_path / "other.duckdb").resolve()
    uri = f"duckdb://{abs_path}"

    resolved = resolve_db_uri(uri, site_root)

    # Absolute path should remain absolute (normalized)
    assert resolved == uri

def test_resolve_db_uri_memory(tmp_path):
    site_root = tmp_path

    uris = [
        "duckdb:///:memory:",
        "duckdb://:memory:",
        "duckdb://memory:",
        "duckdb://memory"
    ]

    for uri in uris:
        assert resolve_db_uri(uri, site_root) == uri

def test_resolve_db_uri_other_scheme(tmp_path):
    site_root = tmp_path

    uri = "postgres://user:pass@host/db"
    assert resolve_db_uri(uri, site_root) == uri

def test_resolve_db_uri_empty(tmp_path):
    assert resolve_db_uri("", tmp_path) == ""
