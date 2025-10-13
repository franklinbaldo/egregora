from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest

from egregora.config import PipelineConfig
from egregora.processor import UnifiedProcessor

HAS_GEMINI_KEY = bool(os.getenv("GEMINI_API_KEY"))


@pytest.mark.skipif(
    not HAS_GEMINI_KEY,
    reason="GEMINI_API_KEY not configured; skipping live Gemini integration test.",
)
def test_pipeline_generates_post_with_live_gemini() -> None:
    workspace = Path("tmp-tests") / f"profiles-{uuid.uuid4().hex}"
    zips_dir = workspace / "zips"
    posts_dir = workspace / "letters"

    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    conversation = """03/10/2025 09:00 - +55 11 99999-1111: Mensagem longa com contexto relevante para o grupo
03/10/2025 09:05 - +55 11 99999-1111: Participação detalhada com ideias e propostas concretas
"""
    zip_path = zips_dir / "Conversa do WhatsApp com Grupo Teste.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Conversa do WhatsApp com Grupo Teste.txt", conversation)

    config = PipelineConfig(
        zip_files=[zip_path],
        posts_dir=posts_dir,
    )

    processor = UnifiedProcessor(config)

    try:
        results = processor.process_all(days=1)
        assert results, "Nenhum post foi gerado pelo pipeline"

        slug, generated_posts = next(iter(results.items()))
        assert generated_posts, "Lista de posts gerados vazia"

        first_post = generated_posts[0]
        assert first_post.exists(), "Arquivo de post não encontrado"

        text = first_post.read_text(encoding="utf-8")
        assert text.strip(), "Conteúdo do post gerado está vazio"
        assert "+55 11 99999-1111" not in text, "Número original não deveria aparecer no post final"
        assert slug  # sanity check on discovered slug
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
