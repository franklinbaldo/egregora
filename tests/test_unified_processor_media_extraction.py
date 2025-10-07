from pathlib import Path
import zipfile
import shutil

import pytest

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor


@pytest.fixture
def config_with_media(tmp_path: Path) -> PipelineConfig:
    """Config with media enabled."""
    # Clean up previous runs
    shutil.rmtree("tests/temp_output", ignore_errors=True)

    # Create directories inside the project directory to avoid ValueError
    zips_dir = Path("tests/temp_output/zips")
    zips_dir.mkdir(parents=True, exist_ok=True)
    newsletters_dir = Path("tests/temp_output/newsletters")
    newsletters_dir.mkdir(parents=True, exist_ok=True)

    # Create a dummy zip file with media
    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w") as f:
        f.write("03/10/2025 09:46 - Franklin: ‎IMG-20251002-WA0004.jpg (arquivo anexado)\n")
    
    media_path = tmp_path / "IMG-20251002-WA0004.jpg"
    with open(media_path, "w") as f:
        f.write("dummy image data")

    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(chat_txt_path, arcname='_chat.txt')
        zf.write(media_path, arcname='IMG-20251002-WA0004.jpg')

    return PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        newsletters_dir=newsletters_dir,
        model="gemini/gemini-1.5-flash-latest",
    )


def test_unified_processor_extracts_media(config_with_media: PipelineConfig, monkeypatch):
    """Verify media is extracted and referenced in newsletter."""

    class MockLLMClient:
        def __init__(self):
            self.models = self
        def generate_content_stream(self, model, contents, config):
            transcript = contents[0].parts[0].text
            class MockStream:
                def __init__(self, text):
                    self.text = text
                def __iter__(self):
                    yield self
            return MockStream(f"Newsletter.\n{transcript}")

    def mock_create_client():
        return MockLLMClient()

    monkeypatch.setattr(
        "egregora.generator.NewsletterGenerator._create_client",
        lambda self: mock_create_client(),
    )

    processor = UnifiedProcessor(config_with_media)
    results = processor.process_all(days=1)

    # Verify media directory exists
    media_output_dir = config_with_media.newsletters_dir / "_chat" / "media"
    assert media_output_dir.exists()

    # Verify media files extracted
    media_files = list(media_output_dir.glob("*"))
    assert len(media_files) > 0

    # Verify markdown links in newsletter
    newsletter_path = results["_chat"][0]
    newsletter_text = newsletter_path.read_text()

    # The filename is now a UUID, so we can't hardcode it.
    # Instead, we check that a markdown image link is present
    # and that the original filename is NOT present.
    assert "![image]" not in newsletter_text  # Should be replaced by the real filename
    assert ".jpg" in newsletter_text  # Check if some image is referenced
    assert "IMG-20251002-WA0004.jpg" not in newsletter_text

    # More robust check: find the new filename and assert its presence
    media_files = list(media_output_dir.glob("*.jpg"))
    assert len(media_files) == 1
    new_filename = media_files[0].name
    assert f"![{new_filename}]" in newsletter_text
