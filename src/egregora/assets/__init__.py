"""Asset management for Egregora."""

from pathlib import Path


def get_demo_chat_path() -> Path:
    """Return the path to the demo chat file."""
    return Path(__file__).parent / "demo_chat.zip"
