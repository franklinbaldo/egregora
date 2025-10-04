"""Shared test fixtures and configuration for egregora testing framework."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Generator

import pytest

from egregora.config import PipelineConfig
from test_framework.helpers import load_real_whatsapp_transcript


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def whatsapp_zip_path() -> Path:
    """Path to the WhatsApp test zip file."""
    return Path("tests/data/Conversa do WhatsApp com Teste.zip")


@pytest.fixture
def whatsapp_real_content(whatsapp_zip_path: Path) -> str:
    """Conversation content extracted from the real WhatsApp test archive."""

    return load_real_whatsapp_transcript(whatsapp_zip_path)


@pytest.fixture
def sample_config(temp_dir: Path) -> PipelineConfig:
    """Create a sample pipeline configuration for testing."""
    return PipelineConfig.with_defaults(
        zips_dir=temp_dir / "zips",
        newsletters_dir=temp_dir / "newsletters",
        media_dir=temp_dir / "media",
        group_name="Test Group",
    )


@pytest.fixture
def setup_test_environment(temp_dir: Path, whatsapp_zip_path: Path) -> Path:
    """Set up a complete test environment with WhatsApp data."""
    # Create necessary directories
    zips_dir = temp_dir / "zips"
    newsletters_dir = temp_dir / "newsletters"
    cache_dir = temp_dir / "cache"
    
    zips_dir.mkdir(parents=True)
    newsletters_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    
    # Copy WhatsApp test file
    test_zip = zips_dir / "2025-10-03.zip"
    if whatsapp_zip_path.exists():
        shutil.copy2(whatsapp_zip_path, test_zip)
    
    return temp_dir


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client for testing without API calls."""
    class MockClient:
        def generate_content(self, prompt: str, **kwargs):
            return MockResponse()
    
    class MockResponse:
        def __init__(self):
            self.text = "Mock newsletter content generated from conversation."
    
    return MockClient()


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    # Set mock API key to prevent actual API calls during tests
    os.environ.setdefault("GEMINI_API_KEY", "test-key-12345")
    yield
    # Cleanup if needed