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


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory within the project tree for tests."""

    base = Path.cwd() / "tmp-tests"
    base.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=base) as tmp:
        yield Path(tmp)


@pytest.fixture
def whatsapp_zip_path() -> Path:
    """Path to the WhatsApp test zip file."""
    return Path("tests/data/Conversa do WhatsApp com Teste.zip")


@pytest.fixture
def whatsapp_test_data() -> str:
    """Raw WhatsApp conversation content for testing."""
    return """03/10/2025 09:45 - As mensagens e ligações são protegidas com a criptografia de ponta a ponta. Somente as pessoas que fazem parte da conversa podem ler, ouvir e compartilhar esse conteúdo. Saiba mais
03/10/2025 09:45 - Você criou este grupo
03/10/2025 09:45 - ‎Iuri Brasil foi adicionado(a)
03/10/2025 09:45 - Você atualizou a duração das mensagens temporárias. Todas as novas mensagens desaparecerão desta conversa ‎24 horas após o envio, exceto se salvas na conversa.
03/10/2025 09:45 - Você removeu Iuri Brasil
03/10/2025 09:45 - Franklin: Teste de grupo
03/10/2025 09:45 - Franklin: 🐱
03/10/2025 09:46 - Franklin: ‎IMG-20251002-WA0004.jpg (arquivo anexado)
03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo"""


@pytest.fixture
def whatsapp_real_content(whatsapp_test_data: str) -> str:
    """Provide WhatsApp conversation content for tests expecting a real transcript."""

    return whatsapp_test_data


@pytest.fixture
def sample_config(temp_dir: Path) -> PipelineConfig:
    """Create a sample pipeline configuration for testing."""
    return PipelineConfig.with_defaults(
        zips_dir=temp_dir / "zips",
        newsletters_dir=temp_dir / "newsletters",
        media_dir=temp_dir / "media",
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