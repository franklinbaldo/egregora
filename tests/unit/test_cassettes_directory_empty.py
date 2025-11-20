from pathlib import Path


def test_cassettes_directory_is_empty():
    """Ensure recorded HTTP cassettes are not reintroduced."""

    cassettes_dir = Path(__file__).resolve().parents[1] / "cassettes"
    if not cassettes_dir.exists():
        return

    cassette_files = [path for path in cassettes_dir.glob("**/*") if path.is_file()]
    assert not cassette_files, f"Remove recorded cassettes: {cassette_files}"
