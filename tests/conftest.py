import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """A fixture that provides a temporary directory for tests."""
    return tmp_path

@pytest.fixture
def whatsapp_zip_path() -> Path:
    """A fixture that provides the path to a test WhatsApp zip file."""
    # This path can be overridden in a local conftest.py if needed
    return Path("tests/data/does_not_exist.zip")