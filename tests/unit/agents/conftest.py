import os
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_google_api_keys():
    """Mock Google API keys to avoid environment variable requirements in tests."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy-key", "GOOGLE_API_KEYS": "dummy-key"}):
        yield
