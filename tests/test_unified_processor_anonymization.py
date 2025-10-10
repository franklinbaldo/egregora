import os
import shutil
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor
from egregora.privacy import PrivacyViolationError


HAS_GEMINI_KEY = bool(os.getenv("GEMINI_API_KEY"))


@pytest.mark.skipif(
    not HAS_GEMINI_KEY,
    reason="GEMINI_API_KEY not configured; skipping live anonymization integration test.",
)
def test_unified_processor_anonymizes_transcripts(tmp_path: Path) -> None:
    base_dir = Path("tests/temp_output/anonymization")
    shutil.rmtree(base_dir, ignore_errors=True)

    zips_dir = base_dir / "zips"
    posts_dir = base_dir / "posts"
    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    zip_path = zips_dir / "Conversa do WhatsApp com Teste.zip"
    chat_txt_path = tmp_path / "_chat.txt"
    with open(chat_txt_path, "w", encoding="utf-8") as handle:
        handle.write("03/10/2025 09:45 - +55 11 94529-4774: Teste de grupo\n")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(chat_txt_path, arcname="_chat.txt")

    config = PipelineConfig.with_defaults(
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        model="gemini/gemini-1.5-flash-latest",
        timezone=ZoneInfo("America/Sao_Paulo"),
    )

    processor = UnifiedProcessor(config)

    try:
        results = processor.process_all(days=1)
    finally:
        chat_txt_path.unlink(missing_ok=True)

    slug, generated_posts = next(iter(results.items()))
    output_file = generated_posts[0]
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    if "+55 11 94529-4774" in content:
        raise PrivacyViolationError("Telefone não deveria aparecer no post gerado")
    assert "Member-" in content or "Membro" in content

    shutil.rmtree(base_dir, ignore_errors=True)
