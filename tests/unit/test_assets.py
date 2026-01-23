from pathlib import Path

from egregora.assets import get_demo_chat_path


def test_get_demo_chat_path_returns_valid_path():
    """Test that get_demo_chat_path returns a path that exists and is a file."""
    path = get_demo_chat_path()
    assert isinstance(path, Path)
    assert path.exists(), f"Demo chat file not found at {path}"
    assert path.is_file(), f"Path at {path} is not a file"
    assert path.name == "demo_chat.zip"


def test_get_demo_chat_path_location():
    """Test that the path is within the egregora package structure."""
    path = get_demo_chat_path()
    # Should be inside src/egregora/assets
    assert "src/egregora/assets" in str(path) or "site-packages/egregora/assets" in str(path)
