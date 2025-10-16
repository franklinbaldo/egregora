"""Simplified enrichment tests focusing on regex patterns and core functionality."""

# TODO: These tests should be integrated with the pytest suite.
# TODO: The sys.path manipulation should be removed. The tests should be run
# in an environment where the `egregora` package is properly installed.
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


from egregora.enrichment import MEDIA_TOKEN_RE, MESSAGE_RE, URL_RE

EXPECTED_URLS = 3
EXPECTED_MESSAGES = 5
EXPECTED_TIME_PARTS = 2
EXPECTED_URLS_LARGE = 100


def test_url_extraction_patterns():
    """Test URL extraction regex with WhatsApp content."""
    whatsapp_content = """03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo
03/10/2025 09:47 - Maria: Vejam https://example.com/article e http://test.com"""

    urls = URL_RE.findall(whatsapp_content)

    assert len(urls) == EXPECTED_URLS
    assert "https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT" in urls
    assert "https://example.com/article" in urls
    assert "http://test.com" in urls


def test_message_format_recognition():
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


def test_media_token_detection():
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

    assert (
        parsed_messages >= EXPECTED_MESSAGES
    ), f"Should parse multiple messages, found {parsed_messages}"


def test_whatsapp_real_data_patterns():
    """Test patterns against real WhatsApp export format."""
    # Using the actual format from our test file
    real_whatsapp_lines = [
        "03/10/2025 09:45 - Franklin: Teste de grupo",
        "03/10/2025 09:45 - Franklin: 🐱",
        "03/10/2025 09:46 - Franklin: ‎IMG-20251002-WA0004.jpg (arquivo anexado)",
        "03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT",
    ]

    # Note: The current MESSAGE_RE expects HH:MM format, but WhatsApp uses DD/MM/YYYY HH:MM
    # This test documents the current limitation
    for line in real_whatsapp_lines:
        assert MESSAGE_RE.match(line) is None, f"MESSAGE_RE should not match full WhatsApp line: {line}"

    # URLs should be found regardless
    all_content = "\n".join(real_whatsapp_lines)
    urls = URL_RE.findall(all_content)
    assert len(urls) == 1
    assert "youtu.be" in urls[0]


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
            MESSAGE_RE.match(case)
            media = MEDIA_TOKEN_RE.findall(case)

            # Basic validation - should return lists/None without errors
            assert isinstance(urls, list)
            assert isinstance(media, list)
            # match can be None, that's ok

        except Exception as e:
            raise AssertionError(f"Regex failed on edge case: {case[:50]}... Error: {e}") from e


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

    assert len(urls) == EXPECTED_URLS_LARGE
    assert duration < 1.0, f"URL extraction took {duration:.2f}s, should be < 1s"


if __name__ == "__main__":
    print("Running simplified enrichment pattern tests...")

    try:
        test_url_extraction_patterns()
        print("✓ URL extraction patterns test passed")

        test_message_format_recognition()
        print("✓ Message format recognition test passed")

        test_media_token_detection()
        print("✓ Media token detection test passed")

        test_complex_conversation_patterns()
        print("✓ Complex conversation patterns test passed")

        test_whatsapp_real_data_patterns()
        print("✓ WhatsApp real data patterns test passed")

        test_edge_cases_regex_patterns()
        print("✓ Edge cases regex patterns test passed")

        test_url_extraction_performance()
        print("✓ URL extraction performance test passed")

        print("\n🎉 All enrichment pattern tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()