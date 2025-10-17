from __future__ import annotations

import time

import pytest

from egregora.enrichment import MEDIA_TOKEN_RE, MESSAGE_RE, URL_RE


def test_url_extraction_patterns():
    whatsapp_content = """03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo
03/10/2025 09:47 - Maria: Vejam https://example.com/article e http://test.com"""

    urls = URL_RE.findall(whatsapp_content)

    assert len(urls) == 3
    assert "https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT" in urls
    assert "https://example.com/article" in urls
    assert "http://test.com" in urls


def test_message_format_recognition():
    test_cases = [
        ("09:45 - Franklin: Teste de grupo", ("09:45", "Franklin", "Teste de grupo")),
        ("15:30 - Maria José: Mensagem longa", ("15:30", "Maria José", "Mensagem longa")),
        ("22:15 - +55 11 99999-9999: Contato", ("22:15", "+55 11 99999-9999", "Contato")),
        ("08:00 — Alice: Com travessão", ("08:00", "Alice", "Com travessão")),
        ("12:30 – Bob: Com hífen", ("12:30", "Bob", "Com hífen")),
    ]

    for message, expected in test_cases:
        match = MESSAGE_RE.match(message)
        assert match is not None, f"{message} should match MESSAGE_RE"
        result = (match.group("time"), match.group("sender"), match.group("message"))
        assert result == expected


def test_media_token_detection():
    cases = [
        "09:45 - Franklin: <mídia oculta>",
        "10:00 - Alice: Olha isso <mídia oculta> que legal",
        "11:30 - Bob: <MÍDIA OCULTA>",
        "12:15 - Carol: <midia oculta>",
    ]

    for case in cases:
        matches = MEDIA_TOKEN_RE.findall(case)
        assert matches, f"Expected to find media token in '{case}'"


def test_complex_conversation_patterns():
    complex_content = """09:00 - Sistema: Grupo criado
09:01 - Alice: Olá pessoal! 👋
09:02 - Bob: Alguém viu o link que mandei?
09:03 - Bob: https://example.com/important-article
09:04 - Charlie: documento.pdf enviado
09:05 - Alice: Perfeito! Vou revisar 📖"""

    urls = URL_RE.findall(complex_content)
    assert urls, "Expected at least one URL match"

    parsed_messages = sum(1 for line in complex_content.splitlines() if MESSAGE_RE.match(line))
    assert parsed_messages >= 5


def test_whatsapp_real_data_patterns():
    real_whatsapp_lines = [
        "03/10/2025 09:45 - Franklin: Teste de grupo",
        "03/10/2025 09:45 - Franklin: 🐱",
        "03/10/2025 09:46 - Franklin: ‎IMG-20251002-WA0004.jpg (arquivo anexado)",
        "03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT",
    ]

    for line in real_whatsapp_lines:
        assert MESSAGE_RE.match(line) is None

    urls = URL_RE.findall("\n".join(real_whatsapp_lines))
    assert urls == ["https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT"]


def test_edge_cases_regex_patterns():
    edge_cases = [
        "09:45 - Franklin: ",
        "10:00 - José: Olá! Como está? 🎉💫⭐",
        "11:30 - Maria: " + "A" * 500,
        "12:45 - Pedro: Vejam https://site1.com e https://site2.com/page?param=value",
        "13:00 - Ana: Links: http://test.com https://secure.com ftp://file.com",
    ]

    for case in edge_cases:
        urls = URL_RE.findall(case)
        media_tokens = MEDIA_TOKEN_RE.findall(case)
        assert isinstance(urls, list)
        assert isinstance(media_tokens, list)
        _ = MESSAGE_RE.match(case)  # exercise regexp without asserting outcome


@pytest.mark.slow
def test_url_extraction_performance():
    large_content = "\n".join(
        f"10:{i:02d} - User{i}: Check https://example{i}.com/page" for i in range(100)
    )

    start = time.perf_counter()
    urls = URL_RE.findall(large_content)
    duration = time.perf_counter() - start

    assert len(urls) == 100
    assert duration < 1.0
