import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor


@pytest.fixture
def config_with_url(tmp_path: Path) -> PipelineConfig:
    """Config with a dummy zip file containing a URL."""
    # Create directories inside the project directory to avoid ValueError
    zips_dir = Path("tests/temp_output/zips")
    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir = Path("tests/temp_output/posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Create a dummy zip file with a URL
    zip_path = zips_dir / "Conversa do WhatsApp com URL.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w") as f:
        f.write("03/10/2025 09:46 - Franklin: Check this: https://example.com\n")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt_path, arcname="_chat.txt")

    return PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model="gemini/gemini-1.5-flash-latest",
    )


@patch("mimetypes.guess_type", return_value=("text/html", None))
def test_urls_preserved_in_post(mock_guess_type, config_with_url: PipelineConfig, monkeypatch):
    """Verify URLs from WhatsApp are present in the final post."""

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

            return MockStream(f"Post.\n{transcript}")

    def mock_create_client():
        return MockLLMClient()

    monkeypatch.setattr(
        "egregora.generator.PostGenerator._create_client",
        lambda self: mock_create_client(),
    )

    processor = UnifiedProcessor(config_with_url)
    results = processor.process_all(days=1)

    post_path = results["_chat"][0]
    post_text = post_path.read_text()
    assert "https://example.com" in post_text
