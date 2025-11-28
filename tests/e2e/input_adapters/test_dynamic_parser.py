from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import WhatsAppFixture

from egregora.input_adapters.whatsapp.dynamic import (
    ParserDefinition,
    generate_dynamic_regex,
)
from tests.e2e.input_adapters.test_whatsapp_adapter import (
    create_export_from_fixture,
)


@pytest.fixture
def mock_agent_run(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    with patch("pydantic_ai.Agent.run_sync") as mock:
        yield mock


def test_dynamic_regex_generator_success(mock_agent_run, minimal_config):
    """Test that the dynamic regex generator can parse a sample and return a valid regex."""
    mock_agent_run.return_value = ParserDefinition(
        regex_pattern=r"^(\d{1,2}/\d{1,2}/\d{4}),\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.*)$"
    )

    sample_lines = [
        "28/10/2025, 15:00 - Franklin: this is a test",
        "28/10/2025, 15:01 - Eurico Max: this is another test",
    ]
    pattern = generate_dynamic_regex(sample_lines, minimal_config)

    assert pattern is not None
    assert pattern.pattern == r"^(\d{1,2}/\d{1,2}/\d{4}),\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.*)$"
    assert pattern.match("28/10/2025, 15:00 - Franklin: this is a test")
    mock_agent_run.assert_called_once()


def test_dynamic_regex_generator_failure(mock_agent_run, minimal_config):
    """Test that the dynamic regex generator returns None if the LLM fails."""
    mock_agent_run.side_effect = Exception("API error")

    sample_lines = ["28/10/2025, 15:00 - Franklin: this is a test"]
    pattern = generate_dynamic_regex(sample_lines, minimal_config)

    assert pattern is None
    mock_agent_run.assert_called_once()


def test_dynamic_regex_caching(mock_agent_run, whatsapp_fixture: WhatsAppFixture, tmp_path: Path):
    """Test that the dynamic regex generator caches the result."""
    from egregora.input_adapters.whatsapp.parsing import (
        ZipMessageSource,
        _get_parser_pattern,
    )

    mock_agent_run.return_value = ParserDefinition(
        regex_pattern=r"^(\d{1,2}/\d{1,2}/\d{4})\s(\d{1,2}:\d{2})\s-\s([^:]+):\s(.*)$"
    )

    export = create_export_from_fixture(whatsapp_fixture)
    source = ZipMessageSource(export)

    # First call, should call the LLM
    pattern1 = _get_parser_pattern(source, cache_dir=tmp_path)
    assert pattern1 is not None
    mock_agent_run.assert_called_once()

    # Second call, should use the cache
    pattern2 = _get_parser_pattern(source, cache_dir=tmp_path)
    assert pattern2 is not None
    # The mock should still only have been called once
    mock_agent_run.assert_called_once()

    assert pattern1.pattern == pattern2.pattern
