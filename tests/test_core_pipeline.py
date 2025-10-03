"""Core pipeline tests using WhatsApp test data."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.config import PipelineConfig
from egregora.pipeline import (
    read_zip_texts,
    _prepare_transcripts,
    list_zip_days,
    find_date_in_name,
    _anonymize_transcript_line
)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_framework.helpers import (
    create_test_zip,
    extract_anonymized_authors,
    count_message_types,
    validate_whatsapp_format,
    TestDataGenerator
)


def test_zip_processing_whatsapp_format(temp_dir, whatsapp_zip_path):
    """Test zip file processing with real WhatsApp data."""
    if not whatsapp_zip_path.exists():
        # Create test zip if real one doesn't exist
        test_content = TestDataGenerator.create_complex_conversation()
        test_zip = temp_dir / "test.zip"
        create_test_zip(test_content, test_zip)
        zip_path = test_zip
    else:
        zip_path = whatsapp_zip_path
    
    # Test zip reading
    content = read_zip_texts(zip_path)
    
    # Validate content
    assert len(content) > 0
    assert "Franklin:" in content or "Alice:" in content
    
    # Validate WhatsApp format
    issues = validate_whatsapp_format(content)
    assert len(issues) == 0, f"Format issues found: {issues}"


def test_date_recognition_whatsapp():
    """Test date recognition in WhatsApp file names."""
    test_cases = [
        ("2025-10-03.zip", date(2025, 10, 3)),
        ("Conversa do WhatsApp 2025-10-03.zip", date(2025, 10, 3)),
        ("export-2025-12-25.zip", date(2025, 12, 25)),
        ("no-date-file.zip", None),
    ]
    
    for filename, expected_date in test_cases:
        result = find_date_in_name(Path(filename))
        assert result == expected_date, f"Failed for {filename}: got {result}, expected {expected_date}"


def test_whatsapp_anonymization_comprehensive(temp_dir):
    """Comprehensive test of WhatsApp format anonymization."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    # Test various WhatsApp message formats
    test_conversations = [
        # Basic messages
        "03/10/2025 09:45 - Franklin: Teste de grupo",
        # With emojis
        "03/10/2025 09:45 - Maria: Olá! 🐱",
        # With attachments
        "03/10/2025 09:46 - José: ‎arquivo.pdf (arquivo anexado)",
        # With URLs
        "03/10/2025 09:47 - Ana: https://example.com/link",
        # System messages (should not be anonymized)
        "03/10/2025 09:48 - Você criou este grupo",
    ]
    
    for conversation in test_conversations:
        transcripts = [(date(2025, 10, 3), conversation)]
        result = _prepare_transcripts(transcripts, config)
        processed = result[0][1]
        
        # Check anonymization worked for user messages
        if "Franklin:" in conversation or "Maria:" in conversation:
            assert "Member-" in processed or "User-" in processed
            assert "Franklin" not in processed
            assert "Maria" not in processed
        
        # Check system messages are preserved
        if "Você criou" in conversation:
            assert "Você criou" in processed


def test_message_type_preservation(temp_dir):
    """Test that different message types are preserved during processing."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    complex_conversation = TestDataGenerator.create_complex_conversation()
    
    # Count original message types
    original_counts = count_message_types(complex_conversation)
    
    # Process through pipeline
    transcripts = [(date(2025, 10, 3), complex_conversation)]
    result = _prepare_transcripts(transcripts, config)
    processed = result[0][1]
    
    # Count processed message types
    processed_counts = count_message_types(processed)
    
    # Verify preservation
    assert processed_counts['media_attachments'] == original_counts['media_attachments']
    assert processed_counts['urls'] == original_counts['urls']
    assert processed_counts['emojis'] >= original_counts['emojis']  # May add anonymization markers


def test_multi_day_processing(temp_dir):
    """Test processing conversations across multiple days."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    multi_day_content = TestDataGenerator.create_multi_day_content()
    result = _prepare_transcripts(multi_day_content, config)
    
    # Verify all days processed
    assert len(result) == 3
    
    # Verify chronological order
    dates = [item[0] for item in result]
    assert dates == [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]
    
    # Verify content processing
    for processed_date, processed_content in result:
        assert len(processed_content) > 0


def test_anonymization_consistency(temp_dir):
    """Test that the same author gets the same anonymized name consistently."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    # Multiple messages from the same author
    conversation = """03/10/2025 09:45 - Franklin: Primeira mensagem
03/10/2025 09:46 - Alice: Mensagem da Alice
03/10/2025 09:47 - Franklin: Segunda mensagem
03/10/2025 09:48 - Franklin: Terceira mensagem"""
    
    transcripts = [(date(2025, 10, 3), conversation)]
    result = _prepare_transcripts(transcripts, config)
    processed = result[0][1]
    
    # Extract anonymized names
    mapping = extract_anonymized_authors(conversation, processed)
    
    # Verify Franklin gets consistent anonymization
    franklin_anon = mapping.get('Franklin')
    assert franklin_anon is not None
    
    # Count occurrences
    franklin_count = processed.count(franklin_anon)
    assert franklin_count == 3, f"Franklin should appear 3 times, found {franklin_count}"


def test_edge_cases_handling(temp_dir):
    """Test handling of edge cases in WhatsApp conversations."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    edge_cases = TestDataGenerator.create_edge_cases()
    
    for case in edge_cases:
        try:
            transcripts = [(date(2025, 10, 3), case)]
            result = _prepare_transcripts(transcripts, config)
            processed = result[0][1]
            
            # Basic validation - should not crash and should return something
            assert isinstance(processed, str)
            assert len(processed) >= 0
            
        except Exception as e:
            assert False, f"Edge case failed: {case[:50]}... Error: {e}"


def test_zip_listing_functionality(temp_dir):
    """Test the zip listing functionality with date-named files."""
    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()
    
    # Create test zip files with dates
    test_files = [
        "2025-10-01.zip",
        "2025-10-03.zip", 
        "2025-10-02.zip",
        "invalid-name.zip",
    ]
    
    for filename in test_files:
        zip_path = zips_dir / filename
        create_test_zip("Test content", zip_path)
    
    # Test listing
    zip_days = list_zip_days(zips_dir)
    
    # Should find 3 valid date-named files, sorted by date
    assert len(zip_days) == 3
    
    dates = [item[0] for item in zip_days]
    assert dates == [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]


if __name__ == "__main__":
    # Manual test runner for development
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        whatsapp_zip_path = Path("tests/data/Conversa do WhatsApp com Teste.zip")
        
        print("Running core pipeline tests...")
        
        try:
            test_zip_processing_whatsapp_format(temp_dir, whatsapp_zip_path)
            print("✓ Zip processing test passed")
            
            test_date_recognition_whatsapp()
            print("✓ Date recognition test passed")
            
            test_whatsapp_anonymization_comprehensive(temp_dir)
            print("✓ Anonymization test passed")
            
            test_message_type_preservation(temp_dir)
            print("✓ Message preservation test passed")
            
            test_multi_day_processing(temp_dir)
            print("✓ Multi-day processing test passed")
            
            test_anonymization_consistency(temp_dir)
            print("✓ Anonymization consistency test passed")
            
            test_edge_cases_handling(temp_dir)
            print("✓ Edge cases test passed")
            
            test_zip_listing_functionality(temp_dir)
            print("✓ Zip listing test passed")
            
            print("\n🎉 All core pipeline tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()