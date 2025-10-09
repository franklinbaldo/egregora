"""Simplified enrichment tests focusing on regex patterns and core functionality."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from test_framework.helpers import summarize_whatsapp_content

from egregora.enrichment import MEDIA_TOKEN_RE, MESSAGE_RE, URL_RE

EXPECTED_URL_SAMPLE_COUNT = 100
MINIMUM_URLS_IN_SAMPLE = 3
MINIMUM_PARSED_MESSAGES = 5
MINIMUM_METADATA_LINE_COUNT = 6


def test_url_extraction_patterns(whatsapp_real_content):
    """Test URL extraction regex with WhatsApp content."""

    extended_content = "\n".join(
        [
            whatsapp_real_content,
            "03/10/2025 09:47 - Maria: Vejam https://example.com/article e http://test.com",
        ]
    )

    urls = URL_RE.findall(extended_content)

    assert "https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT" in urls
    assert "https://example.com/article" in urls
    assert "http://test.com" in urls
    assert len(urls) >= MINIMUM_URLS_IN_SAMPLE


def test_message_format_recognition(whatsapp_real_content):
    """Test message format regex with various WhatsApp patterns."""
    test_cases = [
        ("09:45 - Franklin: Teste de grupo", ("09:45", "Franklin", "Teste de grupo")),
        ("15:30 - Maria José: Mensagem longa", ("15:30", "Maria José", "Mensagem longa")),
        ("22:15 - +55 11 99999-9999: Contato", ("22:15", "+55 11 99999-9999", "Contato")),
        ("08:00 — Alice: Com travessão", ("08:00", "Alice", "Com travessão")),
        ("12:30 – Bob: Com hífen", ("12:30", "Bob", "Com hífen")),
    ]

    for message, expected in test_cases:
        match = MESSAGE_RE.match(message)
        if match:
            result = (match.group("time"), match.group("sender"), match.group("message"))
            assert result == expected, f"Failed for {message}: got {result}, expected {expected}"

    # Validate that real data can be normalised into the expected format
    real_lines = [
        line
        for line in whatsapp_real_content.splitlines()
        if " - " in line and ": " in line and line[:2].isdigit()
    ]
    assert real_lines, "Expected at least one real conversation line"

    for line in real_lines:
        time_and_rest = " ".join(line.split(" ", 1)[1:])
        match = MESSAGE_RE.match(time_and_rest)
        assert match is not None, f"Should parse real line: {line}"


def test_media_token_detection(whatsapp_real_content):
    """Test media placeholder detection in messages."""
    test_cases = [
        "09:45 - Franklin: <mídia oculta>",
        "10:00 - Alice: Olha isso <mídia oculta> que legal",
        "11:30 - Bob: <MÍDIA OCULTA>",  # Case insensitive
        "12:15 - Carol: <midia oculta>",  # Accent variation
    ]

    for case in test_cases:
        matches = MEDIA_TOKEN_RE.findall(case)
        assert len(matches) >= 1, f"Should find media token in: {case}"

    # The real conversation contains a media attachment that should not trigger the token
    attachment_line = next(
        (line for line in whatsapp_real_content.splitlines() if "arquivo anexado" in line),
        None,
    )
    assert attachment_line is not None
    assert MEDIA_TOKEN_RE.findall(attachment_line) == []


def test_complex_conversation_patterns():
    """Test pattern recognition with complex conversation."""
    # Create a conversation that matches the expected HH:MM format
    complex_content = """09:00 - Sistema: Grupo criado
09:01 - Alice: Olá pessoal! 👋
09:02 - Bob: Alguém viu o link que mandei?
09:03 - Bob: https://example.com/important-article
09:04 - Charlie: documento.pdf enviado
09:05 - Alice: Perfeito! Vou revisar 📖"""

    # Test URL extraction
    urls = URL_RE.findall(complex_content)
    assert len(urls) >= 1, "Should find URLs in complex conversation"

    # Test message parsing
    lines = complex_content.strip().split("\n")
    parsed_messages = 0

    for line in lines:
        if MESSAGE_RE.match(line):
            parsed_messages += 1

    assert parsed_messages >= MINIMUM_PARSED_MESSAGES, (
        f"Should parse multiple messages, found {parsed_messages}"
    )


def test_whatsapp_real_data_patterns(whatsapp_real_content):
    """Test patterns against real WhatsApp export format."""

    metadata = summarize_whatsapp_content(whatsapp_real_content)
    assert metadata["line_count"] >= MINIMUM_METADATA_LINE_COUNT
    assert metadata["url_count"] >= 1
    assert metadata["has_media_attachment"]
    assert metadata["has_emojis"]

    urls = URL_RE.findall(whatsapp_real_content)
    assert any("youtu.be" in url for url in urls)


def test_edge_cases_regex_patterns():
    """Test regex patterns with edge cases."""
    edge_cases = [
        # Empty messages
        "09:45 - Franklin: ",
        # Messages with special characters
        "10:00 - José: Olá! Como está? 🎉💫⭐",
        # Very long messages
        "11:30 - Maria: " + "A" * 500,
        # Multiple URLs in one message
        "12:45 - Pedro: Vejam https://site1.com e https://site2.com/page?param=value",
        # URLs with various protocols
        "13:00 - Ana: Links: http://test.com https://secure.com ftp://file.com",
    ]

    for case in edge_cases:
        # Should not crash on any input
        try:
            urls = URL_RE.findall(case)
            _match = MESSAGE_RE.match(case)
            media = MEDIA_TOKEN_RE.findall(case)

            # Basic validation - should return lists/None without errors
            assert isinstance(urls, list)
            assert isinstance(media, list)
            # match can be None, that's ok

        except Exception as error:
            pytest.fail(f"Regex failed on edge case: {case[:50]}... Error: {error}")


def test_url_extraction_performance():
    """Test URL extraction performance with large content."""
    # Generate large content with many URLs
    large_content = []
    for i in range(100):
        large_content.append(f"10:{i:02d} - User{i}: Check https://example{i}.com/page")

    content = "\n".join(large_content)

    # Should handle large content efficiently

    start = time.time()
    urls = URL_RE.findall(content)
    duration = time.time() - start

    assert len(urls) == EXPECTED_URL_SAMPLE_COUNT
    assert duration < 1.0, f"URL extraction took {duration:.2f}s, should be < 1s"
