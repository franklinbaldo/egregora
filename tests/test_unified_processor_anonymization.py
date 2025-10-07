import re
import shutil
import zipfile
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from egregora.config import (
    AnonymizationConfig,
    CacheConfig,
    EnrichmentConfig,
    PipelineConfig,
    RAGConfig,
)
from egregora.processor import UnifiedProcessor


@pytest.fixture
def config_with_anonymization(tmp_path: Path) -> PipelineConfig:
    """Config with anonymization enabled."""
    base_dir = Path("tests/temp_output/anonymization")
    shutil.rmtree(base_dir, ignore_errors=True)
    zips_dir = base_dir / "zips"
    newsletters_dir = base_dir / "newsletters"
    for directory in (zips_dir, newsletters_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # Create a dummy zip file
    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = base_dir / "_chat.txt"
    with open(chat_txt_path, "w") as f:
        f.write("03/10/2025 09:45 - +55 11 94529-4774: Teste de grupo\n")
    
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(chat_txt_path, arcname='_chat.txt')

    return PipelineConfig(
        zips_dir=zips_dir,
        newsletters_dir=newsletters_dir.resolve(),
        anonymization=AnonymizationConfig(enabled=True),
        model="gemini/gemini-1.5-flash-latest",
        timezone=ZoneInfo("America/Sao_Paulo"),
        rag=RAGConfig(enabled=False),
        enrichment=EnrichmentConfig(enabled=False),
        cache=CacheConfig(enabled=False),
    )


def test_unified_processor_anonymizes_e2e(config_with_anonymization: PipelineConfig, monkeypatch):
    """Test that the UnifiedProcessor anonymizes the transcript in an end-to-end test."""

    class MockLLMClient:
        class _Models:
            def generate_content_stream(self, *, model, contents, config):
                # Extract the transcript from the contents
                transcript = contents[0].parts[0].text
                # Check that the transcript is anonymized
                assert "Member-" in transcript
                assert "+55 11 94529-4774" not in transcript
                # Yield a dummy response mimicking streaming chunks
                yield type("Chunk", (), {"text": f"Newsletter.\n{transcript}"})

        def __init__(self):
            self.models = self._Models()

    mock_client = MockLLMClient()
    monkeypatch.setattr(
        "egregora.generator.NewsletterGenerator._create_client",
        lambda self: mock_client,
    )

    processor = UnifiedProcessor(config_with_anonymization)
    processor.process_all(days=1)

    # Check the output file
    output_file = (
        config_with_anonymization.newsletters_dir
        / "_chat"
        / "daily"
        / "2025-10-03.md"
    )
    assert output_file.exists()
    content = output_file.read_text()
    assert "Member-" in content
    assert "+55 11 94529-4774" not in content
