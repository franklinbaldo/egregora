import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.profiles import ParticipantProfile, ProfileUpdater


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
        analysis_version=3,
    )

    data = profile.to_dict()
    clone = ParticipantProfile.from_dict(data)

    assert clone.member_id == profile.member_id
    assert clone.worldview_summary == profile.worldview_summary
    assert clone.core_interests == profile.core_interests
    assert clone.interaction_patterns == profile.interaction_patterns
    assert clone.analysis_version == profile.analysis_version


def test_participant_profile_markdown_contains_interaction_section():
    profile = ParticipantProfile(member_id="Member-XYZ")
    markdown = profile.to_markdown()
    assert "Dinâmica de Participação" in markdown
    assert "Timing de participação" in markdown
