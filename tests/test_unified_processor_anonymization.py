import shutil
import zipfile
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
from egregora.privacy import PrivacyViolationError


@pytest.fixture
def config_with_anonymization(tmp_path: Path) -> PipelineConfig:
    """Config with anonymization enabled."""
    base_dir = Path("tests/temp_output/anonymization")
    shutil.rmtree(base_dir, ignore_errors=True)
    zips_dir = base_dir / "zips"
    posts_dir = base_dir / "posts"
    for directory in (zips_dir, posts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # Create a dummy zip file
    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = base_dir / "_chat.txt"
    with open(chat_txt_path, "w") as f:
        f.write("03/10/2025 09:45 - +55 11 94529-4774: Teste de grupo\n")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt_path, arcname="_chat.txt")

    return PipelineConfig(
        zips_dir=zips_dir,
        posts_dir=posts_dir.resolve(),
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
                yield type("Chunk", (), {"text": f"Post.\n{transcript}"})

        def __init__(self):
            self.models = self._Models()

    mock_client = MockLLMClient()
    monkeypatch.setattr(
        "egregora.generator.PostGenerator._create_client",
        lambda self: mock_client,
    )

    processor = UnifiedProcessor(config_with_anonymization)
    processor.process_all(days=1)

    # Check the output file
    output_file = (
        config_with_anonymization.posts_dir / "_chat" / "posts" / "daily" / "2025-10-03.md"
    )
    assert output_file.exists()
    content = output_file.read_text()
    assert "Member-" in content
    assert "+55 11 94529-4774" not in content

    index_file = config_with_anonymization.posts_dir / "_chat" / "index.md"
    assert index_file.exists()
    index_text = index_file.read_text()
    assert "2025-10-03" in index_text


def test_unified_processor_rejects_phone_leaks(
    config_with_anonymization: PipelineConfig, monkeypatch
) -> None:
    class MockLLMClient:
        class _Models:
            def generate_content_stream(self, *, model, contents, config):
                yield type("Chunk", (), {"text": "Post com contato (4774)."})

        def __init__(self):
            self.models = self._Models()

    monkeypatch.setattr(
        "egregora.generator.PostGenerator._create_client",
        lambda self: MockLLMClient(),
    )

    processor = UnifiedProcessor(config_with_anonymization)

    with pytest.raises(PrivacyViolationError):
        processor.process_all(days=1)
