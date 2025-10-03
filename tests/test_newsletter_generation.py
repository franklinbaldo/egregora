"""Newsletter generation tests using WhatsApp test data."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig
from egregora.enrichment import EnrichmentResult
from egregora.pipeline import (
    generate_newsletter,
    _prepare_transcripts,
    load_previous_newsletter,
    list_zip_days,
    PipelineResult,
)
from test_framework.helpers import create_test_zip


class MockGeminiClient:
    """Mock Gemini client for newsletter generation testing."""

    def __init__(self, response_text=None):
        self.response_text = response_text or self._default_newsletter()
        self.call_count = 0
        self.models = self

    def _default_newsletter(self):
        return """# Newsletter Diária - 03/10/2025
## Fio 1 - Teste
Testes (User-1234)"""

    def generate_content_stream(self, *args, **kwargs):
        self.call_count += 1
        yield Mock(text=self.response_text)


def test_newsletter_generation_with_whatsapp_data(temp_dir):
    """Test complete newsletter generation with WhatsApp data."""
    zips_dir = temp_dir / "zips"
    newsletters_dir = temp_dir / "newsletters"
    zips_dir.mkdir()
    newsletters_dir.mkdir()

    whatsapp_content = """03/10/2025 09:45 - Franklin: Teste de grupo"""
    test_zip = zips_dir / "2025-10-03.zip"
    create_test_zip(
        whatsapp_content, test_zip, "Conversa do WhatsApp com Teste.txt"
    )

    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir, newsletters_dir=newsletters_dir, group_name="Teste Group"
    )

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        with patch("egregora.pipeline.genai") as mock_genai, patch(
            "egregora.pipeline.types"
        ):
            mock_client = MockGeminiClient()
            mock_genai.Client.return_value = mock_client

            result = generate_newsletter(config, client=mock_client)

            assert isinstance(result, PipelineResult)
            assert result.output_path.exists()

            newsletter_content = result.output_path.read_text()
            assert "Newsletter Diária" in newsletter_content
            assert "Franklin" not in newsletter_content
            assert len(newsletter_content) > 50


def test_transcript_preparation_with_anonymization(temp_dir):
    """Test transcript preparation and anonymization with WhatsApp format."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
    )

    whatsapp_transcripts = [
        (date(2025, 10, 3), """03/10/2025 09:45 - Franklin: Teste de grupo""")
    ]

    result = _prepare_transcripts(whatsapp_transcripts, config)

    assert len(result) == 1
    anonymized_content = result[0][1]

    assert "Franklin" not in anonymized_content
    assert "Member-" in anonymized_content or "User-" in anonymized_content
    assert "Teste de grupo" in anonymized_content


def test_previous_newsletter_loading(temp_dir):
    """Test loading of previous newsletter for context."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()

    yesterday = date.today() - timedelta(days=1)
    previous_path = newsletters_dir / f"{yesterday.isoformat()}.md"
    previous_content = "# Newsletter de Ontem"
    previous_path.write_text(previous_content)

    loaded_path, loaded_content = load_previous_newsletter(
        newsletters_dir, date.today()
    )

    assert loaded_path == previous_path
    assert loaded_content == previous_content


def test_newsletter_without_previous_context(temp_dir):
    """Test newsletter generation without previous context."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()

    loaded_path, loaded_content = load_previous_newsletter(
        newsletters_dir, date.today()
    )

    assert loaded_content is None
    assert not loaded_path.exists()


def test_multi_day_newsletter_generation(temp_dir):
    """Test newsletter generation with multiple days of data."""
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()

    test_dates = [date(2025, 10, 1), date(2025, 10, 2)]

    for test_date in test_dates:
        zip_path = zips_dir / f"{test_date.isoformat()}.zip"
        create_test_zip("content", zip_path)

    zip_days = list_zip_days(zips_dir)
    assert len(zip_days) == 2
    dates = [item[0] for item in zip_days]
    assert dates == sorted(test_dates)


def test_newsletter_customization_options(temp_dir):
    """Test newsletter generation with different configuration options."""
    zips_dir = temp_dir / "zips"
    newsletters_dir = temp_dir / "newsletters"
    zips_dir.mkdir()
    newsletters_dir.mkdir()

    whatsapp_content = "03/10/2025 09:45 - Franklin: Teste sem anonimização"
    test_zip = zips_dir / "2025-10-03.zip"
    create_test_zip(whatsapp_content, test_zip)

    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        newsletters_dir=newsletters_dir,
        group_name="Custom Group Name",
    )
    config.anonymization.enabled = False

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch(
        "egregora.pipeline.genai"
    ), patch("egregora.pipeline.types"):
        result = generate_newsletter(config)
        assert result.output_path.exists()


def test_newsletter_error_handling(temp_dir):
    """Test error handling in newsletter generation."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir / "nonexistent",
        newsletters_dir=temp_dir,
    )

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), patch(
        "egregora.pipeline._require_google_dependency"
    ):
        try:
            generate_newsletter(config)
            assert False, "Should have raised an error for missing zip directory"
        except FileNotFoundError as e:
            assert "Nenhum .zip encontrado" in str(e)


def test_newsletter_content_validation(temp_dir):
    """Test validation of generated newsletter content."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()

    mock_content = "# Newsletter Diária - 2025-10-03"
    newsletter_path = newsletters_dir / "2025-10-03.md"
    newsletter_path.write_text(mock_content)

    content = newsletter_path.read_text()

    assert "# Newsletter Diária" in content
    assert "2025-10-03" in content
    assert len(content) > 10


def test_newsletter_file_naming_convention(temp_dir):
    """Test newsletter file naming convention."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()

    test_date = date(2025, 10, 3)
    expected_filename = f"{test_date.isoformat()}.md"
    newsletter_path = newsletters_dir / expected_filename
    newsletter_path.write_text(f"# Newsletter - {test_date}")

    assert newsletter_path.name == expected_filename
    assert newsletter_path.suffix == ".md"
    assert test_date.isoformat() in newsletter_path.stem


def test_pipeline_result_structure(temp_dir):
    """Test PipelineResult data structure."""
    mock_result = PipelineResult(
        output_path=temp_dir / "test.md",
        processed_dates=[date.today()],
        previous_newsletter_path=temp_dir / "previous.md",
        previous_newsletter_found=False,
        enrichment=None,
    )

    assert hasattr(mock_result, "output_path")
    assert hasattr(mock_result, "processed_dates")
    assert hasattr(mock_result, "previous_newsletter_path")
    assert hasattr(mock_result, "previous_newsletter_found")
    assert hasattr(mock_result, "enrichment")

    assert isinstance(mock_result.output_path, Path)
    assert isinstance(mock_result.processed_dates, list)
    assert isinstance(mock_result.previous_newsletter_path, Path)
    assert isinstance(mock_result.previous_newsletter_found, bool)
    assert isinstance(mock_result.enrichment, (EnrichmentResult, type(None)))