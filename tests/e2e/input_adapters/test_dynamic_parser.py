import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from conftest import WhatsAppFixture

from egregora.config import EgregoraConfig
from egregora.input_adapters.whatsapp.dynamic import generate_dynamic_regex
from tests.e2e.input_adapters.test_whatsapp_adapter import (
    create_export_from_fixture,
)


@pytest.fixture
def mock_gemini_client(monkeypatch):
    monkeypatch.setattr(
        "egregora.input_adapters.whatsapp.dynamic.get_google_api_key",
        lambda: "fake-key",
    )
    with patch("google.generativeai.GenerativeModel") as mock:
        yield mock


def test_dynamic_regex_generator_success(mock_gemini_client):
    """Test that the dynamic regex generator can parse a sample and return a valid regex."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {"regex_pattern": r"^(\d{1,2}/\d{1,2}/\d{4}),\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.*)$"}
    )
    mock_gemini_client.return_value.generate_content.return_value = mock_response

    sample_lines = [
        "28/10/2025, 15:00 - Franklin: this is a test",
        "28/10/2025, 15:01 - Eurico Max: this is another test",
    ]
    pattern = generate_dynamic_regex(sample_lines, EgregoraConfig())

    assert pattern is not None
    assert pattern.pattern == r"^(\d{1,2}/\d{1,2}/\d{4}),\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.*)$"
    assert pattern.match("28/10/2025, 15:00 - Franklin: this is a test")


def test_dynamic_regex_generator_failure(mock_gemini_client):
    """Test that the dynamic regex generator returns None if the LLM fails."""
    mock_gemini_client.return_value.generate_content.side_effect = Exception("API error")

    sample_lines = ["28/10/2025, 15:00 - Franklin: this is a test"]
    pattern = generate_dynamic_regex(sample_lines, EgregoraConfig())

    assert pattern is None


def test_dynamic_regex_caching(mock_gemini_client, whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    """Test that the dynamic regex generator caches the result."""
    # This is a bit of a hack, but we need to import the parsing module to test the caching
    from egregora.input_adapters.whatsapp.parsing import ZipMessageSource, _get_parser_pattern

    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {"regex_pattern": r"^(\d{1,2}/\d{1,2}/\d{4})\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.*)$"}
    )
    mock_gemini_client.return_value.generate_content.return_value = mock_response

    export = create_export_from_fixture(whatsapp_fixture)
    source = ZipMessageSource(export)
    sample_lines = list(source.lines())

    # First call, should call the LLM
    pattern1 = _get_parser_pattern(source, cache_dir=tmp_path)
    assert pattern1 is not None
    mock_gemini_client.return_value.generate_content.assert_called_once()

    # Second call, should use the cache
    pattern2 = _get_parser_pattern(source, cache_dir=tmp_path)
    assert pattern2 is not None
    # The mock should still only have been called once
    mock_gemini_client.return_value.generate_content.assert_called_once()

    assert pattern1.pattern == pattern2.pattern
