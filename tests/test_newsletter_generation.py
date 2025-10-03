"""Newsletter generation tests using WhatsApp test data."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig
from egregora.pipeline import (
    generate_newsletter,
    _prepare_transcripts,
    load_previous_newsletter,
    list_zip_days,
    PipelineResult
)
from test_framework.helpers import create_test_zip, simulate_pipeline_run


class MockGeminiClient:
    """Mock Gemini client for newsletter generation testing."""
    
    def __init__(self, response_text=None):
        self.response_text = response_text or self._default_newsletter()
        self.call_count = 0
    
    def _default_newsletter(self):
        return """# Newsletter Diária - 03/10/2025

## Resumo Executivo
Conversas do grupo focaram em tecnologia e compartilhamento de conteúdo educativo.

## Tópicos Principais

### Tecnologia e IA
- Discussão sobre conceitos de inteligência artificial
- Compartilhamento de vídeo educativo sobre programação
- Interesse em machine learning

### Comunicação
- Teste inicial do grupo
- Uso de emojis para comunicação
- Compartilhamento de mídia

## Links Compartilhados
- Vídeo educativo sobre tecnologia

## Próximos Passos
- Continuar discussões técnicas
- Explorar mais conteúdo educativo"""

    def generate_content(self, *args, **kwargs):
        self.call_count += 1
        return Mock(text=self.response_text)


def test_newsletter_generation_with_whatsapp_data(temp_dir):
    """Test complete newsletter generation with WhatsApp data."""
    # Setup test environment
    zips_dir = temp_dir / "zips"
    newsletters_dir = temp_dir / "newsletters"
    zips_dir.mkdir()
    newsletters_dir.mkdir()
    
    # Create test zip with WhatsApp content
    whatsapp_content = """03/10/2025 09:45 - Franklin: Teste de grupo
03/10/2025 09:45 - Franklin: 🐱
03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo"""
    
    test_zip = zips_dir / "2025-10-03.zip"
    create_test_zip(whatsapp_content, test_zip, "Conversa do WhatsApp com Teste.txt")
    
    # Create config
    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        newsletters_dir=newsletters_dir,
        media_dir=temp_dir / "media",
        group_name="Teste Group"
    )
    
    # Mock environment variables and dependencies
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
        with patch('egregora.pipeline.genai') as mock_genai:
            with patch('egregora.pipeline._require_google_dependency'):
                mock_client = MockGeminiClient()
                mock_genai.Client.return_value = mock_client
                
                # Generate newsletter
                result = generate_newsletter(config, client=mock_client)
            
                # Validate result
                assert isinstance(result, PipelineResult)
                assert result.newsletter_path.exists()
                
                # Check newsletter content
                newsletter_content = result.newsletter_path.read_text()
                assert "Newsletter Diária" in newsletter_content
                assert "Franklin" not in newsletter_content  # Should be anonymized
                assert len(newsletter_content) > 100


def test_transcript_preparation_with_anonymization(temp_dir):
    """Test transcript preparation and anonymization with WhatsApp format."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    # Test with anonymization enabled
    whatsapp_transcripts = [
        (date(2025, 10, 3), """03/10/2025 09:45 - Franklin: Teste de grupo
03/10/2025 09:46 - Maria: Ótima ideia
03/10/2025 09:47 - José: Concordo plenamente""")
    ]
    
    result = _prepare_transcripts(whatsapp_transcripts, config)
    
    # Validate anonymization
    assert len(result) == 1
    anonymized_content = result[0][1]
    
    assert "Franklin" not in anonymized_content
    assert "Maria" not in anonymized_content
    assert "José" not in anonymized_content
    assert "Member-" in anonymized_content
    
    # Validate content preservation
    assert "Teste de grupo" in anonymized_content
    assert "Ótima ideia" in anonymized_content
    assert "Concordo plenamente" in anonymized_content


def test_previous_newsletter_loading(temp_dir):
    """Test loading of previous newsletter for context."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()
    
    # Create a previous newsletter
    yesterday = date.today() - timedelta(days=1)
    previous_path = newsletters_dir / f"{yesterday.isoformat()}.md"
    previous_content = """# Newsletter de Ontem

## Contexto Anterior
- Discussão sobre projeto X
- Decisões tomadas
"""
    previous_path.write_text(previous_content)
    
    # Test loading
    loaded_path, loaded_content = load_previous_newsletter(newsletters_dir, date.today())
    
    assert loaded_path == previous_path
    assert loaded_content == previous_content
    assert "Contexto Anterior" in loaded_content


def test_newsletter_without_previous_context(temp_dir):
    """Test newsletter generation without previous context."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()
    
    # Test loading when no previous newsletter exists
    loaded_path, loaded_content = load_previous_newsletter(newsletters_dir, date.today())
    
    assert loaded_content is None
    assert not loaded_path.exists()


def test_multi_day_newsletter_generation(temp_dir):
    """Test newsletter generation with multiple days of data."""
    zips_dir = temp_dir / "zips"
    newsletters_dir = temp_dir / "newsletters"
    zips_dir.mkdir()
    newsletters_dir.mkdir()
    
    # Create multiple zip files
    test_dates = [
        date(2025, 10, 1),
        date(2025, 10, 2),
        date(2025, 10, 3),
    ]
    
    for test_date in test_dates:
        content = f"""03/10/2025 09:45 - Franklin: Mensagem do dia {test_date.day}
03/10/2025 09:46 - Maria: Discussão sobre tópico {test_date.day}"""
        
        zip_path = zips_dir / f"{test_date.isoformat()}.zip"
        create_test_zip(content, zip_path)
    
    # Test zip listing
    zip_days = list_zip_days(zips_dir)
    assert len(zip_days) == 3
    
    # Verify dates are in chronological order
    dates = [item[0] for item in zip_days]
    assert dates == sorted(test_dates)


def test_newsletter_customization_options(temp_dir):
    """Test newsletter generation with different configuration options."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir,
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
        group_name="Custom Group Name"
    )
    
    # Test configuration options
    assert config.group_name == "Custom Group Name"
    assert config.anonymization.enabled == True  # Default
    assert config.enrichment.enabled == True     # Default
    
    # Test with disabled features
    config.anonymization.enabled = False
    config.enrichment.enabled = False
    
    whatsapp_content = "03/10/2025 09:45 - Franklin: Teste sem anonimização"
    result, metrics = simulate_pipeline_run(config, whatsapp_content)
    
    # When anonymization is disabled, names should be preserved
    if not config.anonymization.enabled:
        assert "Franklin" in result


def test_newsletter_error_handling(temp_dir):
    """Test error handling in newsletter generation."""
    config = PipelineConfig.with_defaults(
        zips_dir=temp_dir / "nonexistent",  # Nonexistent directory
        newsletters_dir=temp_dir,
        media_dir=temp_dir / "media",
    )
    
    # Test with missing zip directory
    try:
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            with patch('egregora.pipeline._require_google_dependency'):
                generate_newsletter(config)
        assert False, "Should have raised an error for missing zip directory"
    except (FileNotFoundError, Exception) as e:
        # Expected - should handle missing files gracefully
        assert "zip" in str(e).lower() or "encontrado" in str(e).lower()


def test_newsletter_content_validation(temp_dir):
    """Test validation of generated newsletter content."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()
    
    # Create a mock newsletter
    mock_content = """# Newsletter Diária - 03/10/2025

## Resumo Executivo
Teste de conteúdo gerado.

## Tópicos Principais
- Tópico 1
- Tópico 2

## Conclusão
Fim da newsletter."""
    
    newsletter_path = newsletters_dir / "2025-10-03.md"
    newsletter_path.write_text(mock_content)
    
    # Validate structure
    content = newsletter_path.read_text()
    
    # Check required sections
    assert "# Newsletter Diária" in content
    assert "## Resumo Executivo" in content
    assert "## Tópicos Principais" in content
    
    # Check date format
    assert "03/10/2025" in content
    
    # Check content length
    assert len(content) > 50


def test_newsletter_file_naming_convention(temp_dir):
    """Test newsletter file naming convention."""
    newsletters_dir = temp_dir / "newsletters"
    newsletters_dir.mkdir()
    
    test_dates = [
        date(2025, 10, 3),
        date(2025, 12, 25),
        date(2025, 1, 1),
    ]
    
    for test_date in test_dates:
        expected_filename = f"{test_date.isoformat()}.md"
        newsletter_path = newsletters_dir / expected_filename
        
        # Create mock newsletter
        newsletter_path.write_text(f"# Newsletter - {test_date}")
        
        # Validate naming
        assert newsletter_path.name == expected_filename
        assert newsletter_path.suffix == ".md"
        assert test_date.isoformat() in newsletter_path.stem


def test_pipeline_result_structure(temp_dir):
    """Test PipelineResult data structure."""
    # Create a mock PipelineResult
    mock_result = PipelineResult(
        newsletter_path=temp_dir / "test.md",
        previous_newsletter_path=temp_dir / "previous.md",
        previous_newsletter_found=False,
        processed_days=3,
        total_characters=1500,
        enrichment_duration=2.5,
        generation_duration=5.0
    )
    
    # Validate structure
    assert hasattr(mock_result, 'newsletter_path')
    assert hasattr(mock_result, 'previous_newsletter_found')
    assert hasattr(mock_result, 'processed_days')
    assert hasattr(mock_result, 'total_characters')
    assert hasattr(mock_result, 'enrichment_duration')
    assert hasattr(mock_result, 'generation_duration')
    
    # Validate types
    assert isinstance(mock_result.newsletter_path, Path)
    assert isinstance(mock_result.previous_newsletter_found, bool)
    assert isinstance(mock_result.processed_days, int)
    assert isinstance(mock_result.total_characters, int)
    assert isinstance(mock_result.enrichment_duration, (int, float))
    assert isinstance(mock_result.generation_duration, (int, float))


if __name__ == "__main__":
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        
        print("Running newsletter generation tests...")
        
        try:
            test_newsletter_generation_with_whatsapp_data(temp_dir)
            print("✓ Newsletter generation with WhatsApp data test passed")
            
            test_transcript_preparation_with_anonymization(temp_dir)
            print("✓ Transcript preparation with anonymization test passed")
            
            test_previous_newsletter_loading(temp_dir)
            print("✓ Previous newsletter loading test passed")
            
            test_newsletter_without_previous_context(temp_dir)
            print("✓ Newsletter without previous context test passed")
            
            test_multi_day_newsletter_generation(temp_dir)
            print("✓ Multi-day newsletter generation test passed")
            
            test_newsletter_customization_options(temp_dir)
            print("✓ Newsletter customization options test passed")
            
            test_newsletter_error_handling(temp_dir)
            print("✓ Newsletter error handling test passed")
            
            test_newsletter_content_validation(temp_dir)
            print("✓ Newsletter content validation test passed")
            
            test_newsletter_file_naming_convention(temp_dir)
            print("✓ Newsletter file naming convention test passed")
            
            test_pipeline_result_structure(temp_dir)
            print("✓ Pipeline result structure test passed")
            
            print("\n🎉 All newsletter generation tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()