"""Shared test fixtures and configuration for egregora testing framework."""

from __future__ import annotations

import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Generator

import pytest

from egregora.config import PipelineConfig


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    base_dir = Path.cwd()
    with tempfile.TemporaryDirectory(dir=base_dir) as tmp:
        yield Path(tmp)


@pytest.fixture
def whatsapp_zip_path() -> Path:
    """Path to the WhatsApp test zip file."""
    return Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")


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
def sample_config(temp_dir: Path) -> PipelineConfig:
    """Create a sample pipeline configuration for testing."""
    return PipelineConfig.with_defaults(
        zips_dir=temp_dir / "zips",
        posts_dir=temp_dir / "posts",
        group_name="Test Group",
    )


@pytest.fixture
def setup_test_environment(temp_dir: Path, whatsapp_zip_path: Path) -> Path:
    """Set up a complete test environment with WhatsApp data."""
    # Create necessary directories
    zips_dir = temp_dir / "zips"
    posts_dir = temp_dir / "posts"
    cache_dir = temp_dir / "cache"
    
    zips_dir.mkdir(parents=True)
    posts_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    
    # Copy WhatsApp test file
    test_zip = zips_dir / "2025-10-03.zip"
    if whatsapp_zip_path.exists():
        shutil.copy2(whatsapp_zip_path, test_zip)
    
    return temp_dir





@pytest.fixture
def whatsapp_real_content() -> str:
    """Return a longer WhatsApp conversation sample used in integration tests."""

    sample_path = Path("tests/data/Conversa do WhatsApp com Teste.txt")
    return sample_path.read_text(encoding="utf-8")
