"""Helper functions and utilities for egregora testing."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

ASCII_THRESHOLD = 127


def create_test_zip(content: str, zip_path: Path, filename: str = "conversation.txt") -> None:
    """Create a test zip file with conversation content."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(filename, content)


def extract_anonymized_authors(original: str, anonymized: str) -> dict[str, str]:
    """Extract mapping of original authors to anonymized names."""
    mapping = {}
    orig_lines = original.strip().split("\n")
    anon_lines = anonymized.strip().split("\n")

    for orig, anon in zip(orig_lines, anon_lines, strict=False):
        if ": " in orig and ": " in anon:
            orig_author = orig.split(": ")[0].split(" - ")[-1]
            anon_author = anon.split(": ")[0].split(" - ")[-1]
            if orig_author != anon_author:
                mapping[orig_author] = anon_author

    return mapping


def count_message_types(content: str) -> dict[str, int]:
    """Count different types of messages in WhatsApp content."""
    lines = content.strip().split("\n")
    counts = {
        "user_messages": 0,
        "system_messages": 0,
        "media_attachments": 0,
        "urls": 0,
        "emojis": 0,
    }

    for line in lines:
        if ": " in line and " - " in line:
            # User message
            counts["user_messages"] += 1
            if "arquivo anexado" in line:
                counts["media_attachments"] += 1
            if "http" in line:
                counts["urls"] += 1
            # Simple emoji detection
            if any(ord(char) > ASCII_THRESHOLD for char in line):
                counts["emojis"] += 1
        else:
            # System message
            counts["system_messages"] += 1

    return counts


def validate_whatsapp_format(content: str) -> list[str]:
    """Validate WhatsApp conversation format and return any issues."""
    issues = []
    lines = content.strip().split("\n")

    for i, line in enumerate(lines, 1):
        # Check for basic format
        if not line.strip():
            continue

        # Skip file headers added by egregora
        if line.startswith("# Arquivo:"):
            continue

        # Look for date pattern or system messages
        if not (
            line.startswith(("0", "1", "2", "3"))
            or line.startswith(" -")
            or "Você" in line
            or "As mensagens" in line
            or "‎" in line
        ):
            issues.append(f"Line {i}: Unexpected format - {line[:50]}...")

    return issues


class TestDataGenerator:
    """Generate various test scenarios for comprehensive testing."""

    @staticmethod
    def create_multi_day_content() -> list[tuple[date, str]]:
        """Create multi-day conversation content for testing."""
        return [
            (date(2025, 10, 1), "01/10/2025 10:00 - Alice: Bom dia pessoal!"),
            (date(2025, 10, 2), "02/10/2025 15:30 - Bob: Como foi o dia?"),
            (date(2025, 10, 3), "03/10/2025 09:45 - Franklin: Teste de grupo"),
        ]

    @staticmethod
    def create_complex_conversation() -> str:
        """Create a complex conversation with various message types."""
        return """03/10/2025 09:00 - Sistema: Grupo criado
03/10/2025 09:01 - Alice: Olá pessoal! 👋
03/10/2025 09:02 - Bob: Alguém viu o link que mandei?
03/10/2025 09:03 - Bob: https://example.com/important-article
03/10/2025 09:04 - Charlie: ‎documento.pdf (arquivo anexado)
03/10/2025 09:05 - Alice: Perfeito! Vou revisar 📖
03/10/2025 09:06 - David: +55 11 99999-9999 é meu contato
03/10/2025 09:07 - Eve: Meu email é eve@example.com"""

    @staticmethod
    def create_edge_cases() -> list[str]:
        """Create edge case scenarios for robust testing."""
        return [
            # Empty lines
            "03/10/2025 09:45 - Franklin: \n\n03/10/2025 09:46 - Alice: Teste",
            # Special characters
            "03/10/2025 09:45 - José: Olá! Como está? 🎉💫⭐",
            # Long messages
            "03/10/2025 09:45 - Maria: " + "A" * 1000,
            # Multiple URLs
            "03/10/2025 09:45 - Pedro: https://site1.com e https://site2.com",
        ]
