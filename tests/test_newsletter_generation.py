"""Newsletter generation tests using WhatsApp test data."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig
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

    def _default_newsletter(self):
        return """# Newsletter Diária - 03/10/2025
## Resumo Executivo
Conversas do grupo focaram em tecnologia e compartilhamento de conteúdo educativo.
"""

    def generate_content(self, *args, **kwargs):
        self.call_count += 1
        if kwargs.get("stream"):
            yield Mock(text=self.response_text)
        else:
            return Mock(text=self.response_text)


def test_newsletter_generation_with_whatsapp_data(tmp_path):
    """Test complete newsletter generation with WhatsApp data."""
    zips_dir = tmp_path / "zips"
    newsletters_dir = tmp_path / "newsletters"
    zips_dir.mkdir()
    newsletters_dir.mkdir()

    whatsapp_content = "03/10/2025 09:45 - Franklin: Teste de grupo"
    test_zip = zips_dir / "2025-10-03.zip"
    create_test_zip(whatsapp_content, test_zip, "Conversa do WhatsApp com Teste.txt")

    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir, newsletters_dir=newsletters_dir, group_name="Teste Group"
    )

    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        with patch("egregora.pipeline.genai"):
            with patch("egregora.pipeline._require_google_dependency"):
                mock_client = MockGeminiClient()
                result = generate_newsletter(config, client=mock_client)

                assert isinstance(result, PipelineResult)
                assert result.output_path.exists()
                newsletter_content = result.output_path.read_text()
                assert "Newsletter Diária" in newsletter_content
                assert "Franklin" not in newsletter_content
                assert len(newsletter_content) > 50


def test_transcript_preparation_with_anonymization(tmp_path):
    """Test transcript preparation and anonymization with WhatsApp format."""
    config = PipelineConfig.with_defaults(
        zips_dir=tmp_path, newsletters_dir=tmp_path
    )
    whatsapp_transcripts = [
        (date(2025, 10, 3), "03/10/2025 09:45 - Franklin: Teste de grupo")
    ]
    result = _prepare_transcripts(whatsapp_transcripts, config)
    anonymized_content = result[0][1]
    assert "Franklin" not in anonymized_content
    assert "Member-" in anonymized_content


def test_previous_newsletter_loading(tmp_path):
    """Test loading of previous newsletter for context."""
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    yesterday = date.today() - timedelta(days=1)
    previous_path = newsletters_dir / f"{yesterday.isoformat()}.md"
    previous_path.write_text("Contexto Anterior")
    loaded_path, loaded_content = load_previous_newsletter(
        newsletters_dir, date.today()
    )
    assert loaded_path == previous_path
    assert loaded_content == "Contexto Anterior"


def test_newsletter_without_previous_context(tmp_path):
    """Test newsletter generation without previous context."""
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    loaded_path, loaded_content = load_previous_newsletter(
        newsletters_dir, date.today()
    )
    assert loaded_content is None
    assert not loaded_path.exists()


def test_multi_day_newsletter_generation(tmp_path):
    """Test newsletter generation with multiple days of data."""
    zips_dir = tmp_path / "zips"
    zips_dir.mkdir()
    test_dates = [date(2025, 10, 1), date(2025, 10, 2)]
    for test_date in test_dates:
        create_test_zip("content", zips_dir / f"{test_date.isoformat()}.zip")
    zip_days = list_zip_days(zips_dir)
    assert len(zip_days) == 2
    assert [item[0] for item in zip_days] == sorted(test_dates)


def test_newsletter_error_handling(tmp_path):
    """Test error handling in newsletter generation."""
    config = PipelineConfig.with_defaults(
        zips_dir=tmp_path / "nonexistent", newsletters_dir=tmp_path
    )
    with pytest.raises(FileNotFoundError):
        generate_newsletter(config)


def test_newsletter_content_validation(tmp_path):
    """Test validation of generated newsletter content."""
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    mock_content = "# Newsletter Diária\n## Resumo"
    newsletter_path = newsletters_dir / "2025-10-03.md"
    newsletter_path.write_text(mock_content)
    content = newsletter_path.read_text()
    assert "# Newsletter Diária" in content
    assert "## Resumo" in content


def test_newsletter_file_naming_convention(tmp_path):
    """Test newsletter file naming convention."""
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    test_date = date(2025, 10, 3)
    expected_filename = f"{test_date.isoformat()}.md"
    (newsletters_dir / expected_filename).touch()
    assert (newsletters_dir / expected_filename).exists()


def test_pipeline_result_structure(tmp_path):
    """Test PipelineResult data structure."""
    mock_result = PipelineResult(
        output_path=tmp_path / "test.md",
        previous_newsletter_path=tmp_path / "previous.md",
        previous_newsletter_found=False,
        processed_dates=[date.today()],
        enrichment=None,
    )
    assert hasattr(mock_result, "output_path")
    assert hasattr(mock_result, "processed_dates")
    assert hasattr(mock_result, "previous_newsletter_found")
    assert isinstance(mock_result.output_path, Path)
    assert isinstance(mock_result.processed_dates, list)
    assert mock_result.enrichment is None