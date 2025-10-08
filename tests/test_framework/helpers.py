"""Helper functions and utilities for egregora testing."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

import polars as pl
from egregora.anonymizer import Anonymizer, FormatType
from egregora.config import PipelineConfig
from egregora.io import read_zip_texts_and_media
from egregora.models import WhatsAppExport
from egregora.parser import parse_multiple
from egregora.transcript import render_transcript


def create_test_zip(content: str, zip_path: Path, filename: str = "conversation.txt") -> None:
    """Create a test zip file with conversation content."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(filename, content)


def extract_anonymized_authors(original: str, anonymized: str) -> Dict[str, str]:
    """Extract mapping of original authors to anonymized names."""
    mapping = {}
    orig_lines = original.strip().split('\n')
    anon_lines = anonymized.strip().split('\n')
    
    for orig, anon in zip(orig_lines, anon_lines):
        if ': ' in orig and ': ' in anon:
            orig_author = orig.split(': ')[0].split(' - ')[-1]
            anon_author = anon.split(': ')[0].split(' - ')[-1]
            if orig_author != anon_author:
                mapping[orig_author] = anon_author
    
    return mapping


def count_message_types(content: str) -> Dict[str, int]:
    """Count different types of messages in WhatsApp content."""
    lines = content.strip().split('\n')
    counts = {
        'user_messages': 0,
        'system_messages': 0,
        'media_attachments': 0,
        'urls': 0,
        'emojis': 0
    }
    
    for line in lines:
        if ': ' in line and ' - ' in line:
            # User message
            counts['user_messages'] += 1
            if 'arquivo anexado' in line:
                counts['media_attachments'] += 1
            if 'http' in line:
                counts['urls'] += 1
            # Simple emoji detection
            if any(ord(char) > 127 for char in line):
                counts['emojis'] += 1
        else:
            # System message
            counts['system_messages'] += 1
    
    return counts


def validate_whatsapp_format(content: str) -> List[str]:
    """Validate WhatsApp conversation format and return any issues."""
    issues = []
    lines = content.strip().split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for basic format
        if not line.strip():
            continue
        
        # Skip file headers added by egregora
        if line.startswith('# Arquivo:'):
            continue
            
        # Look for date pattern or system messages
        if not (line.startswith(('0', '1', '2', '3')) or line.startswith(' -') or 
                'Você' in line or 'As mensagens' in line or '‎' in line):
            issues.append(f"Line {i}: Unexpected format - {line[:50]}...")
    
    return issues


def load_real_whatsapp_transcript(zip_path: Path) -> str:
    """Load the transcript from a WhatsApp export zip file."""

    if not zip_path.exists():
        raise FileNotFoundError(f"WhatsApp export not found: {zip_path}")

    transcript, _ = read_zip_texts_and_media(zip_path)
    return transcript


def summarize_whatsapp_content(content: str) -> Dict[str, Any]:
    """Return basic statistics extracted from WhatsApp conversation text."""

    lines = [line for line in content.splitlines() if line.strip()]
    url_count = len(re.findall(r"https?://\S+", content))
    has_media_attachment = any("arquivo anexado" in line.lower() for line in lines)
    has_emojis = any(any(ord(ch) > 127 for ch in line) for line in lines)

    authors: set[str] = set()
    for line in lines:
        if " - " not in line or ": " not in line:
            continue
        try:
            _, rest = line.split(" - ", 1)
            author, _ = rest.split(": ", 1)
        except ValueError:
            continue
        author = author.strip()
        if author and author.lower() not in {"sistema", "você"}:
            authors.add(author)

    return {
        "line_count": len(lines),
        "url_count": url_count,
        "has_media_attachment": has_media_attachment,
        "has_emojis": has_emojis,
        "authors": sorted(authors),
    }


class TestDataGenerator:
    """Generate various test scenarios for comprehensive testing."""
    
    @staticmethod
    def create_multi_day_content() -> List[Tuple[date, str]]:
        """Create multi-day conversation content for testing."""
        return [
            (date(2025, 10, 1), "01/10/2025 10:00 - Alice: Bom dia pessoal!"),
            (date(2025, 10, 2), "02/10/2025 15:30 - Bob: Como foi o dia?"),
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
    def create_edge_cases() -> List[str]:
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


def run_pipeline_for_test(
    conversation_tuples: list[tuple[date, str]], config: PipelineConfig, temp_dir: Path
) -> list[tuple[date, str]]:
    """Helper to run the new DataFrame-based pipeline for testing."""
    exports = []
    for i, (day, content) in enumerate(conversation_tuples):
        zip_path = temp_dir / f"test_{i}.zip"
        create_test_zip(content, zip_path, filename="_chat.txt")
        exports.append(
            WhatsAppExport(
                zip_path=zip_path,
                chat_file="_chat.txt",
                group_slug=f"test_{i}",
                group_name=f"Test Group {i}",
                export_date=day,
                media_files=[],
            )
        )

    df = parse_multiple(exports)

    if config.anonymization.enabled:
        df = Anonymizer.anonymize_transcript_dataframe(
            df, format=config.anonymization.output_format
        )

    processed_transcripts = []
    if not df.is_empty():
        for day_df in df.partition_by("date", maintain_order=True):
            text = render_transcript(day_df, use_tagged=False)
            processed_transcripts.append((day_df.get_column("date")[0], text))

    return processed_transcripts


__all__ = [
    "create_test_zip",
    "extract_anonymized_authors",
    "count_message_types",
    "validate_whatsapp_format",
    "load_real_whatsapp_transcript",
    "summarize_whatsapp_content",
    "TestDataGenerator",
    "run_pipeline_for_test",
]