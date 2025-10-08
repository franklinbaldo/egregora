from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest

from egregora.config import (
    AnonymizationConfig,
    CacheConfig,
    EnrichmentConfig,
    PipelineConfig,
    ProfilesConfig,
    RAGConfig,
)
from egregora.profiles import ParticipantProfile, ProfileUpdater
from egregora.processor import UnifiedProcessor


def test_profile_generation_writes_json_and_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = Path("tmp-tests") / f"profiles-{uuid.uuid4().hex}"
    zips_dir = workspace / "zips"
    posts_dir = workspace / "letters"
    profiles_dir = workspace / "profiles_data"
    profiles_docs_dir = workspace / "profiles_docs"

    for directory in (zips_dir, posts_dir, profiles_dir, profiles_docs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    conversation = """03/10/2025 09:00 - +55 11 99999-1111: Mensagem longa com contexto relevante para o grupo
03/10/2025 09:05 - +55 11 99999-1111: Participação detalhada com ideias e propostas concretas
"""
    zip_path = zips_dir / "Conversa do WhatsApp com Grupo Teste.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Conversa do WhatsApp com Grupo Teste.txt", conversation)

    config = PipelineConfig(
        zips_dir=zips_dir,
        posts_dir=posts_dir,
        enrichment=EnrichmentConfig(enabled=False),
        cache=CacheConfig(enabled=False),
        anonymization=AnonymizationConfig(enabled=True),
        rag=RAGConfig(enabled=False),
        profiles=ProfilesConfig(
            enabled=True,
            profiles_dir=profiles_dir,
            docs_dir=profiles_docs_dir,
            min_messages=1,
            min_words_per_message=1,
        ),
    )

    monkeypatch.setattr(
        "egregora.generator.PostGenerator.generate",
        lambda self, source, context: "Post de teste",
        raising=False,
    )
    monkeypatch.setattr(
        "egregora.processor.UnifiedProcessor._get_profiles_client",
        lambda self: object(),
        raising=False,
    )

    async def fake_should_update_profile(self, member_id, current_profile, full_conversation, gemini_client):
        return True, "Perfil precisa ser atualizado", ["Destaque"], ["Insight"]

    async def fake_rewrite_profile(
        self,
        member_id,
        old_profile,
        recent_conversations,
        participation_highlights,
        interaction_insights,
        gemini_client,
    ):
        analysis_version = (old_profile.analysis_version if old_profile else 0) + 1
        profile = ParticipantProfile(
            member_id=member_id,
            worldview_summary="Nova visão",
            markdown_document=f"# Perfil Analítico: {member_id}\n\nSíntese gerada em teste.",
            analysis_version=analysis_version,
        )
        profile.values_and_priorities.append("Colaboração")
        return profile

    monkeypatch.setattr(
        ProfileUpdater,
        "should_update_profile",
        fake_should_update_profile,
        raising=False,
    )
    monkeypatch.setattr(
        ProfileUpdater,
        "rewrite_profile",
        fake_rewrite_profile,
        raising=False,
    )
    monkeypatch.setattr(
        ProfileUpdater,
        "should_update_profile_dataframe",
        lambda self, member_id, current_profile, df: (True, "ok"),
        raising=False,
    )

    processor = UnifiedProcessor(config)
    processor.process_all(days=1)

    group_dir = posts_dir / "grupo-teste"
    json_files = list((group_dir / "profiles" / "json").glob("*.json"))
    assert json_files, "Nenhum perfil JSON foi gerado"

    profile_data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert profile_data["member_id"].startswith("Member-")
    assert profile_data["analysis_version"] == 1
    assert "Colaboração" in profile_data["values_and_priorities"]
    assert profile_data["markdown_document"].startswith("# Perfil Analítico")

    index_path = group_dir / "profiles" / "index.md"
    assert index_path.exists()
    index_text = index_path.read_text(encoding="utf-8")
    assert "Resumo automatizado" in index_text
    assert profile_data["member_id"] not in index_text
    assert "docs/profiles/generated" in index_text

    generated_path = group_dir / "profiles" / "generated" / f"{json_files[0].stem}.md"
    assert generated_path.exists()
    generated_text = generated_path.read_text(encoding="utf-8")
    assert profile_data["member_id"] in generated_text
    assert "[!NOTE]" in generated_text

    assert (group_dir / "media").exists()

    shutil.rmtree(workspace, ignore_errors=True)
