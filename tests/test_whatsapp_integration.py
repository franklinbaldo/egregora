"""Integration tests for WhatsApp conversation processing."""

from __future__ import annotations

import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.config import PipelineConfig
from egregora.pipeline import _prepare_transcripts, read_zip_texts_and_media


def test_whatsapp_zip_processing(tmp_path) -> None:
    """Test that WhatsApp zip files are properly processed."""
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")

    # Test zip reading
    posts_dir = tmp_path / "posts"
    result, media_files = read_zip_texts_and_media(
        zip_path,
        archive_date=date(2025, 10, 3),
        output_dir=posts_dir,
        group_slug="grupo-teste",
    )

    # Verify content is extracted correctly
    assert "Franklin: Teste de grupo" in result
    assert "Franklin: 🐱" in result
    assert "Franklin: Legal esse vídeo" in result

    # Verify media was renamed and referenced correctly
    original_filename = "IMG-20251002-WA0004.jpg"
    assert original_filename in media_files
    media = media_files[original_filename]

    expected_link = f"![{media.filename}]({media.relative_path})"
    assert expected_link in result
    assert media.dest_path.exists()
    assert (posts_dir / "grupo-teste" / "media" / media.filename).exists()

    assert "https://youtu.be/Nkhp-mb6FRc" in result


def test_whatsapp_format_anonymization(tmp_path) -> None:
    """Test anonymization of WhatsApp conversation format."""
    workspace = Path("tmp-tests") / f"whatsapp-{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=True)

    posts_root = workspace / "posts"
    posts_root.mkdir(parents=True, exist_ok=True)
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=posts_root,
    )

    # WhatsApp format: DD/MM/YYYY HH:MM - Author: Message
    whatsapp_transcript = """03/10/2025 09:45 - Franklin: Teste de grupo
03/10/2025 09:45 - Franklin: 🐱
03/10/2025 09:46 - Franklin: Legal esse vídeo
03/10/2025 09:45 - ‎Iuri Brasil foi adicionado(a)
03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT"""

    transcripts = [(date(2025, 10, 3), whatsapp_transcript)]

    # Test with anonymization enabled
    result = _prepare_transcripts(transcripts, config)
    anonymized_text = result[0][1]

    # Check that usernames are anonymized
    print("Original:", whatsapp_transcript)
    print("Anonymized:", anonymized_text)

    # Verify anonymization works correctly
    assert "Franklin" not in anonymized_text  # Should be anonymized
    assert "Member-" in anonymized_text  # Should use anonymized names

    # For now, just verify content preservation
    assert "Teste de grupo" in anonymized_text
    assert "🐱" in anonymized_text
    assert "Legal esse vídeo" in anonymized_text


def test_whatsapp_real_data_end_to_end(tmp_path) -> None:
    """End-to-end test with real WhatsApp zip file."""
    zip_path = Path("tests/data/zips/Conversa do WhatsApp com Teste.zip")

    # Read the zip
    workspace = Path("tmp-tests") / f"whatsapp-{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=True)

    posts_root = workspace / "posts"
    posts_root.mkdir(parents=True, exist_ok=True)
    content, _ = read_zip_texts_and_media(
        zip_path,
        archive_date=date(2025, 10, 3),
        output_dir=posts_root,
        group_slug="grupo",
    )

    # Create config
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=posts_root,
    )

    # Process with anonymization
    transcripts = [(date(2025, 10, 3), content)]
    result = _prepare_transcripts(transcripts, config)

    processed_content = result[0][1]

    # Verify content is preserved
    assert "Teste de grupo" in processed_content
    assert "Legal esse vídeo" in processed_content
    assert "🐱" in processed_content

    # Verify file header is included
    assert "# Arquivo: Conversa do WhatsApp com Teste.txt" in processed_content

    shutil.rmtree(workspace, ignore_errors=True)

    shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    # Run tests manually
    from pathlib import Path

    tmp_path = Path("/tmp/test_egregora")
    tmp_path.mkdir(exist_ok=True)

    print("Running WhatsApp integration tests...")

    print("\n1. Testing zip processing...")
    test_whatsapp_zip_processing(tmp_path)
    print("✓ Zip processing test passed")

    print("\n2. Testing format anonymization...")
    test_whatsapp_format_anonymization(tmp_path)
    print("✓ Format anonymization test passed")

    print("\n3. Testing end-to-end processing...")
    test_whatsapp_real_data_end_to_end(tmp_path)
    print("✓ End-to-end test passed")

    print("\n🎉 All WhatsApp integration tests passed!")
