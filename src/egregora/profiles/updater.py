"""Logic for determining when and how to update participant profiles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from .profile import ParticipantProfile
from .prompts import PROFILE_REWRITE_PROMPT, UPDATE_DECISION_PROMPT


@dataclass(slots=True)
class ProfileUpdater:
    """High level orchestrator that talks to Gemini to maintain profiles."""

    min_messages: int = 2
    min_words_per_message: int = 15

    async def should_update_profile(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        full_conversation: str,
        gemini_client: genai.Client,
    ) -> Tuple[bool, str, List[str], List[str]]:
        """Decide if *member_id* warrants a profile refresh."""

        if gemini_client is None:
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada ou o cliente não foi inicializado."
            )

        member_messages = self._extract_member_messages(member_id, full_conversation)
        meaningful = [msg for msg in member_messages if self._is_meaningful(msg)]

        if len(meaningful) < self.min_messages:
            return False, "Participação mínima hoje", [], []

        if not current_profile or not current_profile.worldview_summary:
            return True, "Primeiro perfil sendo criado", [], []

        profile_markdown = current_profile.to_markdown()
        prompt = UPDATE_DECISION_PROMPT.format(
            member_id=member_id,
            current_profile=profile_markdown,
            full_conversation=full_conversation,
        )

        response = await gemini_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )

        raw_text = getattr(response, "text", "")
        if not raw_text:
            raise ValueError("Resposta vazia do modelo ao decidir atualização do perfil.")

        try:
            decision = json.loads(raw_text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Resposta inválida do modelo ao decidir atualização: {exc}")

        return (
            bool(decision.get("should_update", False)),
            str(decision.get("reasoning", "")),
            list(decision.get("participation_highlights", [])),
            list(decision.get("interaction_insights", [])),
        )

    async def rewrite_profile(
        self,
        member_id: str,
        old_profile: ParticipantProfile | None,
        recent_conversations: Sequence[str],
        participation_highlights: Sequence[str],
        interaction_insights: Sequence[str],
        gemini_client: genai.Client,
    ) -> ParticipantProfile:
        """Request a full profile rewrite based on recent context."""

        if gemini_client is None:
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada ou o cliente não foi inicializado."
            )

        old_profile_text = (
            old_profile.to_markdown() if old_profile else "Nenhum perfil anterior registrado."
        )

        conversations_formatted = self._format_recent_conversations(recent_conversations)
        highlights_block = self._format_bullets(participation_highlights)
        insights_block = self._format_bullets(interaction_insights)

        prompt = PROFILE_REWRITE_PROMPT.format(
            member_id=member_id,
            old_profile=old_profile_text,
            recent_conversations=conversations_formatted,
            participation_highlights=highlights_block,
            interaction_insights=insights_block,
        )

        response = await gemini_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

        raw_text = getattr(response, "text", "")
        if not raw_text:
            raise ValueError("Resposta vazia do modelo ao reescrever o perfil.")

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Resposta inválida do modelo ao reescrever o perfil: {exc}")

        analysis_version = (old_profile.analysis_version if old_profile else 0) + 1

        profile = ParticipantProfile(
            member_id=member_id,
            worldview_summary=str(payload.get("worldview_summary", "")),
            core_interests=dict(payload.get("core_interests", {})),
            thinking_style=str(payload.get("thinking_style", "")),
            values_and_priorities=list(payload.get("values_and_priorities", [])),
            expertise_areas=dict(payload.get("expertise_areas", {})),
            contribution_style=str(payload.get("contribution_style", "")),
            argument_patterns=list(payload.get("argument_patterns", [])),
            questioning_approach=str(payload.get("questioning_approach", "")),
            intellectual_influences=list(payload.get("intellectual_influences", [])),
            aligns_with=list(payload.get("aligns_with", [])),
            debates_with=list(payload.get("debates_with", [])),
            recent_shifts=list(payload.get("recent_shifts", [])),
            growing_interests=list(payload.get("growing_interests", [])),
            interaction_patterns=dict(payload.get("interaction_patterns", {})),
            analysis_version=analysis_version,
        )
        profile.update_timestamp()
        return profile

    def _extract_member_messages(self, member_id: str, conversation: str) -> List[str]:
        pattern = re.compile(rf"\b{re.escape(member_id)}\s*:\s*(.*)")
        messages: List[str] = []
        for line in conversation.splitlines():
            match = pattern.search(line)
            if match:
                messages.append(match.group(1).strip())
        return messages

    def _is_meaningful(self, message: str) -> bool:
        words = [chunk for chunk in re.split(r"\s+", message.strip()) if chunk]
        return len(words) >= self.min_words_per_message

    def _format_recent_conversations(self, conversations: Sequence[str]) -> str:
        if not conversations:
            return "(Sem conversas recentes registradas.)"

        formatted: list[str] = []
        start_index = max(len(conversations) - 5, 0)
        for idx, conv in enumerate(conversations[start_index:], start=1):
            formatted.append(f"## Sessão {idx}\n{conv.strip()}\n")
        return "\n".join(formatted)

    def _format_bullets(self, items: Sequence[str]) -> str:
        if not items:
            return "- (Sem registros para hoje.)"
        return "\n".join(f"- {item}" for item in items)
