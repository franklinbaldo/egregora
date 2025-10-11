"""Simplified post generation tests focusing on testable components."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from egregora.config import PipelineConfig
from egregora.pipeline import (
    _prepare_transcripts,
    load_previous_post,
    list_zip_days,
    find_date_in_name,
    _format_transcript_section_header,
)
from test_framework.helpers import create_test_zip


def test_whatsapp_transcript_preparation(temp_dir, whatsapp_test_data):
    """Test transcript preparation with WhatsApp data."""
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=temp_dir,
    )
    
    # Real WhatsApp conversation
    whatsapp_transcripts = [(date(2025, 10, 3), whatsapp_test_data)]

    # Process transcripts
    result = _prepare_transcripts(whatsapp_transcripts, config)
    
    # Validate processing
    assert len(result) == 1
    processed_date, processed_content = result[0]
    
    # Check date preservation
    assert processed_date == date(2025, 10, 3)
    
    # Check anonymization of authors (in "- Author:" format)
    # Content within messages is preserved as-is
    lines = processed_content.split('\n')
    for line in lines:
        if ' - ' in line and ': ' in line:
            author_part = line.split(' - ')[1].split(':')[0]
            # Authors should be anonymized
            assert author_part.startswith('Member-')
            assert 'Franklin' not in author_part
            assert 'Maria' not in author_part
            assert 'José' not in author_part
    
    # Check content preservation
    assert "Teste de grupo" in processed_content
    assert "🐱" in processed_content
    assert "Ótima ideia" in processed_content


def test_previous_post_context_loading(temp_dir):
    """Test loading the previous post for context."""
    posts_dir = temp_dir / "posts"
    posts_dir.mkdir()

    # Create previous post
    yesterday = date.today() - timedelta(days=1)
    previous_path = posts_dir / f"{yesterday.isoformat()}.md"

    previous_content = """# Post anterior - {yesterday}

## Contexto do Dia Anterior
- Discussão sobre projeto Alpha
- Decisões sobre implementação
- Próximos passos definidos

## Tópicos Importantes
- Tecnologia escolhida
- Timeline do projeto
""".format(yesterday=yesterday.strftime("%d/%m/%Y"))

    previous_path.write_text(previous_content)

    # Test loading
    loaded_path, loaded_content = load_previous_post(posts_dir, date.today())
    
    # Validate loading
    assert loaded_path == previous_path
    assert loaded_content == previous_content
    assert "Contexto do Dia Anterior" in loaded_content
    assert "projeto Alpha" in loaded_content
    

def test_previous_post_skips_gaps(temp_dir):
    """The loader should return the most recent available post even with gaps."""

    posts_dir = temp_dir / "posts_with_gaps"
    posts_dir.mkdir()

    reference_date = date(2025, 10, 10)
    two_days_ago = reference_date - timedelta(days=2)
    three_days_ago = reference_date - timedelta(days=3)

    (posts_dir / f"{three_days_ago.isoformat()}.md").write_text(
        "# Post antigo\n\nAinda relevante", encoding="utf-8"
    )
    (posts_dir / f"{two_days_ago.isoformat()}.md").write_text(
        "# Post de controle\n\nUsado para preencher o gap", encoding="utf-8"
    )

    # Delete yesterday's post to simulate a missing publication.
    missing_yesterday = posts_dir / f"{(reference_date - timedelta(days=1)).isoformat()}.md"
    if missing_yesterday.exists():
        missing_yesterday.unlink()

    loaded_path, loaded_content = load_previous_post(posts_dir, reference_date)

    assert loaded_path.name == f"{two_days_ago.isoformat()}.md"
    assert "Post de controle" in (loaded_content or "")

    # When limiting the search window the function should honour it.
    limited_path, limited_content = load_previous_post(
        posts_dir, reference_date, search_window_days=1
    )
    assert limited_path.name == f"{(reference_date - timedelta(days=1)).isoformat()}.md"
    assert limited_content is None


def test_previous_post_rejects_invalid_window(temp_dir):
    """A zero or negative search window is a misuse and must fail fast."""

    posts_dir = temp_dir / "posts_invalid"
    posts_dir.mkdir()

    with pytest.raises(ValueError):
        load_previous_post(posts_dir, date.today(), search_window_days=0)


def test_post_without_previous_context(temp_dir):
    """Test behavior when no previous post exists."""
    posts_dir = temp_dir / "posts_empty"
    posts_dir.mkdir()

    # Test with empty directory
    loaded_path, loaded_content = load_previous_post(posts_dir, date.today())

    assert loaded_content is None
    assert not loaded_path.exists()

    # Test with non-matching dates
    wrong_date = posts_dir / "2020-01-01.md"
    wrong_date.write_text("Old post")

    loaded_path, loaded_content = load_previous_post(posts_dir, date.today())
    assert loaded_content is None


def test_zip_file_date_detection_and_listing(temp_dir):
    """Test zip file date detection and listing functionality."""
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()
    
    # Create test zip files with various naming patterns
    test_files = [
        ("2025-10-01.zip", date(2025, 10, 1)),
        ("2025-10-03.zip", date(2025, 10, 3)),
        ("2025-10-02.zip", date(2025, 10, 2)),
        ("export-2025-12-25.zip", date(2025, 12, 25)),
        ("invalid-name.zip", None),
        ("Conversa do WhatsApp 2025-11-15.zip", date(2025, 11, 15)),
    ]
    
    for filename, expected_date in test_files:
        zip_path = zips_dir / filename
        create_test_zip("Test content", zip_path)
        
        # Test individual date detection
        detected_date = find_date_in_name(zip_path)
        assert detected_date == expected_date, f"Failed for {filename}: got {detected_date}, expected {expected_date}"
    
    # Test zip listing and sorting
    zip_days = list_zip_days(zips_dir)
    
    # Should find all files with valid dates, sorted chronologically
    expected_valid_dates = [
        date(2025, 10, 1),
        date(2025, 10, 2), 
        date(2025, 10, 3),
        date(2025, 11, 15),
        date(2025, 12, 25),
    ]
    
    assert len(zip_days) == len(expected_valid_dates)
    actual_dates = [item[0] for item in zip_days]
    assert actual_dates == expected_valid_dates


def test_multi_day_transcript_processing(temp_dir, whatsapp_test_data):
    """Test processing transcripts from multiple days."""
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=temp_dir,
    )
    
    # Create multi-day transcripts
    multi_day_transcripts = [
        (date(2025, 10, 1), "01/10/2025 10:00 - Alice: Primeiro dia de conversas"),
        (date(2025, 10, 2), "02/10/2025 14:30 - Bob: Segundo dia, continuando discussão"),
        (date(2025, 10, 3), whatsapp_test_data),
    ]
    
    # Process all transcripts
    result = _prepare_transcripts(multi_day_transcripts, config)
    
    # Validate processing
    assert len(result) == 3
    
    # Check chronological order
    dates = [item[0] for item in result]
    assert dates == [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]
    
    # Check content processing
    for processed_date, processed_content in result:
        assert len(processed_content) > 0
        # All names should be anonymized
        assert "Alice" not in processed_content
        assert "Bob" not in processed_content
        assert "Charlie" not in processed_content
        assert "Member-" in processed_content


def test_transcript_section_headers(temp_dir):
    """Test transcript section header formatting."""
    # Test different transcript counts
    test_cases = [
        (1, "TRANSCRITO BRUTO DO ÚLTIMO DIA"),
        (2, "TRANSCRITO BRUTO DOS ÚLTIMOS 2 DIAS"),
        (5, "TRANSCRITO BRUTO DOS ÚLTIMOS 5 DIAS"),
    ]
    
    for count, expected_text in test_cases:
        header = _format_transcript_section_header(count)
        assert expected_text in header
        assert "CRONOLÓGICA" in header


def test_whatsapp_content_with_special_characters(temp_dir):
    """Test processing WhatsApp content with special characters and media."""
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=temp_dir,
    )
    
    # WhatsApp content with various special elements
    complex_whatsapp = [
        (date(2025, 10, 3), """03/10/2025 09:45 - Franklin: Olá pessoal! 👋🎉
03/10/2025 09:46 - Maria: Como está? 😊
03/10/2025 09:47 - José: ‎IMG-20251002-WA0004.jpg (arquivo anexado)
03/10/2025 09:48 - Ana: https://example.com/artigo-importante
03/10/2025 09:49 - Pedro: Gostei do link da Ana! 🔗""")
    ]
    
    result = _prepare_transcripts(complex_whatsapp, config)
    processed_content = result[0][1]
    
    # Validate emoji preservation
    assert "👋" in processed_content
    assert "😊" in processed_content
    assert "🔗" in processed_content
    
    # Validate media attachment preservation
    assert "arquivo anexado" in processed_content
    
    # Validate URL preservation
    assert "https://example.com" in processed_content
    
    # Validate anonymization still works
    assert "Franklin" not in processed_content
    assert "Member-" in processed_content


def test_anonymization_consistency_across_days(temp_dir):
    """Test that anonymization is consistent across multiple days."""
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=temp_dir,
    )
    
    # Same person across multiple days
    multi_day_same_person = [
        (date(2025, 10, 1), "01/10/2025 10:00 - Franklin: Mensagem do dia 1"),
        (date(2025, 10, 2), "02/10/2025 15:00 - Franklin: Mensagem do dia 2"), 
        (date(2025, 10, 3), "03/10/2025 09:00 - Franklin: Mensagem do dia 3"),
    ]
    
    result = _prepare_transcripts(multi_day_same_person, config)
    
    # Extract anonymized names from each day
    anonymized_names = []
    for processed_date, processed_content in result:
        lines = processed_content.split('\n')
        for line in lines:
            if "Member-" in line and ":" in line:
                # Extract the anonymized name
                name_part = line.split(' - ')[1].split(':')[0]
                if name_part.startswith('Member-'):
                    anonymized_names.append(name_part)
    
    # All instances of Franklin should get the same anonymized name
    unique_names = set(anonymized_names)
    assert len(unique_names) == 1, f"Expected 1 unique name, got {len(unique_names)}: {unique_names}"


def test_config_validation_with_whatsapp_setup(temp_dir):
    """Test configuration validation for WhatsApp processing."""
    # Test valid configuration
    config = PipelineConfig.with_defaults(
        zip_files=[],
        output_dir=temp_dir / "posts",
        group_name="WhatsApp Test Group"
    )
    
    # Validate configuration
    assert config.posts_dir.name == "posts"
    assert config.group_name == "WhatsApp Test Group"
    assert config.anonymization.enabled == True
    assert config.enrichment.enabled == True
    
    # Test configuration customization
    config.anonymization.output_format = "short"
    config.enrichment.enabled = False
    
    assert config.anonymization.output_format == "short"
    assert config.enrichment.enabled == False


if __name__ == "__main__":
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        
        print("Running simplified post generation tests...")
        
        try:
            test_whatsapp_transcript_preparation(temp_dir)
            print("✓ WhatsApp transcript preparation test passed")
            
            test_previous_post_context_loading(temp_dir)
            print("✓ Previous post context loading test passed")

            test_post_without_previous_context(temp_dir)
            print("✓ Post without previous context test passed")
            
            test_zip_file_date_detection_and_listing(temp_dir)
            print("✓ Zip file date detection and listing test passed")
            
            test_multi_day_transcript_processing(temp_dir)
            print("✓ Multi-day transcript processing test passed")
            
            test_transcript_section_headers(temp_dir)
            print("✓ Transcript section headers test passed")
            
            test_whatsapp_content_with_special_characters(temp_dir)
            print("✓ WhatsApp content with special characters test passed")
            
            test_anonymization_consistency_across_days(temp_dir)
            print("✓ Anonymization consistency across days test passed")
            
            test_config_validation_with_whatsapp_setup(temp_dir)
            print("✓ Config validation with WhatsApp setup test passed")
            
            print("\n🎉 All simplified post generation tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
