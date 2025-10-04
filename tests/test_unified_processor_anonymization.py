import re
from pathlib import Path
from datetime import date
import zipfile
from zoneinfo import ZoneInfo

import pytest

try:  # pragma: no cover - optional dependency guard
    import polars  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - skip module when polars missing
    pytest.skip("polars is required for UnifiedProcessor anonymization tests", allow_module_level=True)

from egregora.config import AnonymizationConfig, PipelineConfig, RAGConfig, EnrichmentConfig, CacheConfig
from egregora.processor import UnifiedProcessor


@pytest.fixture
def config_with_anonymization(tmp_path: Path) -> PipelineConfig:
    """Config with anonymization enabled."""
    zips_dir = tmp_path / "zips"
    zips_dir.mkdir()
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # Create a dummy zip file
    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w") as f:
        f.write("03/10/2025 09:45 - +55 11 94529-4774: Teste de grupo\n")
    
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(chat_txt_path, arcname='_chat.txt')

    return PipelineConfig(
        zips_dir=zips_dir,
        newsletters_dir=newsletters_dir.resolve(),
        media_dir=media_dir,
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
        "egregora.pipeline.create_client",
        lambda api_key=None: mock_client,
    )

    processor = UnifiedProcessor(config_with_anonymization)
    processor.process_all(days=1)

    # Check the output file
    output_file = config_with_anonymization.newsletters_dir / "_chat" / "2025-10-03.md"
    assert output_file.exists()
    content = output_file.read_text()
    assert "Member-" in content
    assert "+55 11 94529-4774" not in content
