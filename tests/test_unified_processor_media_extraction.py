import os
import shutil
import zipfile
from pathlib import Path

import pytest

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor


HAS_GEMINI_KEY = bool(os.getenv("GEMINI_API_KEY"))


@pytest.mark.skip(reason="Group discovery is temporarily disabled")
@pytest.mark.skipif(
    not HAS_GEMINI_KEY,
    reason="GEMINI_API_KEY not configured; skipping media extraction integration test.",
)
def test_unified_processor_extracts_media(tmp_path: Path) -> None:
    shutil.rmtree("tests/temp_output", ignore_errors=True)

    zips_dir = Path("tests/temp_output/zips")
    posts_dir = Path("tests/temp_output/posts")
    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w", encoding="utf-8") as handle:
        handle.write("03/10/2025 09:46 - Franklin: ‎IMG-20251002-WA0004.jpg (arquivo anexado)\n")

    media_path = tmp_path / "IMG-20251002-WA0004.jpg"
    with open(media_path, "w", encoding="utf-8") as handle:
        handle.write("dummy image data")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt_path, arcname="_chat.txt")
        zf.write(media_path, arcname="IMG-20251002-WA0004.jpg")

    config = PipelineConfig(
        zip_files=[],
        posts_dir=posts_dir,
        model="gemini/gemini-1.5-flash-latest",
    )

    processor = UnifiedProcessor(config)
    results = processor.process_all(days=1)

    media_output_dir = posts_dir / "_chat" / "media"
    assert media_output_dir.exists()

    media_files = list(media_output_dir.glob("*.jpg"))
    assert media_files, "Nenhum arquivo de mídia foi extraído"

    post_path = results["_chat"][0]
    post_text = post_path.read_text(encoding="utf-8")
    assert "## Mídias Compartilhadas" in post_text
    assert "IMG-20251002-WA0004.jpg" not in post_text
    extracted_name = media_files[0].name
    assert extracted_name in post_text

    shutil.rmtree("tests/temp_output", ignore_errors=True)
