import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.profiles import ParticipantProfile, ProfileUpdater
from egregora.profiles.updater import _extract_summary_from_markdown


def test_should_update_profile_requires_meaningful_participation():
    updater = ProfileUpdater(min_messages=2, min_words_per_message=3)
    conversation = """
    09:00 - Member-AAAA: Olá
    09:05 - Member-BBBB: Vamos começar analisando os dados?
    09:07 - Member-AAAA: Sim
    """.strip()

    should_update, reasoning, highlights, insights = asyncio.run(
        updater.should_update_profile(
            member_id="Member-AAAA",
            current_profile=None,
            full_conversation=conversation,
            gemini_client=object(),  # not used because of early return
        )
    )

    assert not should_update
    assert reasoning == "Participação mínima hoje"
    assert highlights == []
    assert insights == []


def test_extract_member_messages_handles_context():
    updater = ProfileUpdater()
    conversation = """
    09:15 - Member-A1B2: Primeira mensagem do dia.
    09:17 - Member-C3D4: Outra pessoa fala algo.
    09:20 - Member-A1B2: Responde com mais contexto e detalhes relevantes.
    """.strip()

    messages = updater._extract_member_messages("Member-A1B2", conversation)
    assert messages == [
        "Primeira mensagem do dia.",
        "Responde com mais contexto e detalhes relevantes.",
    ]


def test_participant_profile_serialization_round_trip():
    profile = ParticipantProfile(
        member_id="Member-ABCD",
        worldview_summary="Analisa temas estratégicos em profundidade.",
        core_interests={"tecnologia": ["IA", "automação"]},
        thinking_style="Constrói sínteses a partir de tensões opostas.",
        values_and_priorities=["equidade", "transparência"],
        expertise_areas={"economia": "macrotendências"},
        contribution_style="Atua como facilitador de debates complexos.",
        argument_patterns=["Questiona premissas implícitas"],
        questioning_approach="Faz perguntas abertas para mapear possibilidades.",
        intellectual_influences=["Bell Hooks"],
        aligns_with=["Member-0001"],
        debates_with=["Member-0002"],
        recent_shifts=["Aprofundou foco em política industrial"],
        growing_interests=["Governança de IA"],
        interaction_patterns={
            "participation_timing": "Entra cedo para ancorar discussões.",
            "response_style": "Escuta antes de sintetizar.",
            "influence_on_group": "Orientador de rumo estratégico.",
        },
        markdown_document="# Perfil Analítico: Member-ABCD\n\nResumo de teste.",
        analysis_version=3,
    )

    data = profile.to_dict()
    clone = ParticipantProfile.from_dict(data)

    assert clone.member_id == profile.member_id
    assert clone.worldview_summary == profile.worldview_summary
    assert clone.core_interests == profile.core_interests
    assert clone.interaction_patterns == profile.interaction_patterns
    assert clone.markdown_document == profile.markdown_document
    assert clone.analysis_version == profile.analysis_version


def test_participant_profile_markdown_contains_interaction_section():
    profile = ParticipantProfile(member_id="Member-XYZ")
    markdown = profile.to_markdown()
    assert "Dinâmica de Participação" in markdown
    assert "Timing de participação" in markdown


def test_should_update_profile_dataframe_with_polars() -> None:
    updater = ProfileUpdater(min_messages=2, min_words_per_message=3)
    df = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 1, 9, 10),
                datetime(2024, 1, 1, 9, 20),
            ],
            "date": [date(2024, 1, 1)] * 3,
            "author": [
                "Member-AAAA",
                "Member-AAAA",
                "Member-BBBB",
            ],
            "message": [
                "Mensagem detalhada com múltiplas palavras relevantes",
                "Outra contribuição com contexto suficiente para análise",
                "Intervenção breve de outro membro",
            ],
        }
    )

    existing_profile = ParticipantProfile(member_id="Member-AAAA", worldview_summary="Ativo")

    should_update, reason = updater.should_update_profile_dataframe(
        "Member-AAAA", existing_profile, df
    )

    assert should_update
    assert "mensagens significativas" in reason


def test_participation_stats_dataframe_computes_metrics() -> None:
    updater = ProfileUpdater()
    df = pl.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 1, 9, 30),
                datetime(2024, 1, 2, 10, 0),
            ],
            "date": [date(2024, 1, 1), date(2024, 1, 1), date(2024, 1, 2)],
            "author": ["Member-AAAA", "Member-AAAA", "Member-AAAA"],
            "message": [
                "Primeira mensagem com conteúdo relevante",
                "Segunda mensagem com detalhes adicionais",
                "Resumo do dia anterior com próximos passos",
            ],
        }
    )

    stats = updater.get_participation_stats_dataframe("Member-AAAA", df)

    expected_total_messages = 3
    expected_active_days = 2
    reference_day = date(2024, 1, 1)

    assert stats["total_messages"] == expected_total_messages
    assert stats["active_days"] == expected_active_days
    assert stats["most_active_day"] == reference_day


def test_extract_summary_from_markdown() -> None:
    markdown = """# Perfil Analítico: Member-123

## Visão Geral
Contribui com análises estratégicas e provoca debates aprofundados.

## Participação Recente
- Ponto
"""
    summary = _extract_summary_from_markdown(markdown)
    assert "análises estratégicas" in summary.lower()
