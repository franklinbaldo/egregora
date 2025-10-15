"""Logic for determining when and how to update participant profiles."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

import polars as pl

from .profile import ParticipantProfile
from .prompts import PROFILE_REWRITE_PROMPT, UPDATE_DECISION_PROMPT


def _extract_summary_from_markdown(markdown: str) -> str:
    capture = False
    collected: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if capture and collected:
                break
            continue
        if line.startswith("#"):
            normalized = line.lstrip("#").strip().lower()
            if normalized.startswith("visão geral"):
                capture = True
                collected.clear()
                continue
            if capture:
                break
            continue
        if capture:
            collected.append(line)
    if collected:
        return " ".join(collected).strip()
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def _ensure_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple | set):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in value]
    except TypeError:
        return [str(value)]


@dataclass(slots=True)
class ProfileUpdater:
    """High level orchestrator that talks to Gemini to maintain profiles."""

    min_messages: int = 2
    min_words_per_message: int = 15
    decision_model: str = "models/gemini-flash-latest"
    rewrite_model: str = "models/gemini-flash-latest"
    max_api_retries: int = 3
    minimum_retry_seconds: float = 30.0

    async def should_update_profile(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        full_conversation: str,
        gemini_client: genai.Client,
    ) -> tuple[bool, str, list[str], list[str]]:
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

        response = await self._generate_with_retry(
            gemini_client,
            model=self.decision_model,
            contents=prompt,
            temperature=0.3,
        )

        raw_text = getattr(response, "text", "")
        if not raw_text:
            raise ValueError("Resposta vazia do modelo ao decidir atualização do perfil.")

        try:
            decision = json.loads(raw_text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Resposta inválida do modelo ao decidir atualização: {exc}") from exc

        highlights = _ensure_str_list(decision.get("participation_highlights"))
        insights = _ensure_str_list(decision.get("interaction_insights"))

        return (
            bool(decision.get("should_update", False)),
            str(decision.get("reasoning", "")),
            highlights,
            insights,
        )

    async def rewrite_profile(  # noqa: PLR0913
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

        response = await self._generate_with_retry(
            gemini_client,
            model=self.rewrite_model,
            contents=prompt,
            temperature=0.7,
        )

        markdown = getattr(response, "text", "")
        if not markdown and getattr(response, "candidates", None):  # pragma: no cover - defensive
            parts = response.candidates[0].content.parts  # type: ignore[attr-defined]
            markdown = "".join(getattr(part, "text", "") or "" for part in parts)

        markdown = (markdown or "").strip()
        if markdown.startswith("{"):
            try:
                payload = json.loads(markdown)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                candidate = payload.get("profile") or payload.get("markdown")
                if isinstance(candidate, str):
                    markdown = candidate.strip()

        if not markdown:
            raise ValueError("Resposta vazia do modelo ao reescrever o perfil.")

        analysis_version = (old_profile.analysis_version if old_profile else 0) + 1
        summary = _extract_summary_from_markdown(markdown)
        summary = summary or "Perfil gerado automaticamente; personalize se necessário."

        profile = ParticipantProfile(
            member_id=member_id,
            worldview_summary=summary,
            values_and_priorities=_ensure_str_list(participation_highlights),
            argument_patterns=_ensure_str_list(interaction_insights),
            markdown_document=markdown,
            analysis_version=analysis_version,
        )
        profile.update_timestamp()
        return profile

    async def _generate_with_retry(
        self,
        client: genai.Client,
        *,
        model: str,
        contents: str,
        temperature: float,
    ):
        attempt = 0
        last_exc: Exception | None = None
        while attempt < max(self.max_api_retries, 1):
            attempt += 1
            try:
                return await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        response_mime_type="application/json",
                    ),
                )
            except Exception as exc:  # pragma: no cover - depends on API behaviour
                last_exc = exc
                delay = self._extract_retry_delay(exc)
                if delay is None or attempt >= self.max_api_retries:
                    break
                await asyncio.sleep(max(delay, self.minimum_retry_seconds))
        raise last_exc if last_exc is not None else RuntimeError("Unknown error calling Gemini API")

    @staticmethod
    def _extract_retry_delay(exc: Exception) -> float | None:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" not in message:
            return None

        match = re.search(r"retryDelay['\"]?\s*[:=]\s*'?(\d+)(?:\.(\d+))?s", message)
        if match:
            whole = match.group(1)
            frac = match.group(2) or ""
            return float(f"{whole}.{frac}" if frac else whole)

        match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message)
        if match:
            return float(match.group(1))

        return None

    def _extract_member_messages(self, member_id: str, conversation: str) -> list[str]:
        pattern = re.compile(rf"\b{re.escape(member_id)}\s*:\s*(.*)")
        messages: list[str] = []
        for line in conversation.splitlines():
            match = pattern.search(line)
            if match:
                messages.append(match.group(1).strip())
        return messages

    def extract_member_messages_dataframe(
        self,
        member_id: str,
        df: pl.DataFrame,
    ) -> pl.DataFrame:
        """Extract messages from a specific member using Polars operations."""

        if "author" not in df.columns:
            raise KeyError("DataFrame must have 'author' column")

        return df.filter(pl.col("author") == member_id)

    def should_update_profile_dataframe(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        df: pl.DataFrame,
    ) -> tuple[bool, str]:
        """Decide if member warrants profile refresh using DataFrame analysis."""

        messages_df = self.extract_member_messages_dataframe(member_id, df)

        if "message" not in messages_df.columns:
            raise KeyError("DataFrame must have 'message' column")

        if messages_df.is_empty():
            return False, "Nenhuma mensagem encontrada"

        messages_with_counts = messages_df.with_columns(self._word_count_expression())

        meaningful_messages = messages_with_counts.filter(
            pl.col("word_count") >= self.min_words_per_message
        )
        meaningful_count = meaningful_messages.height

        if meaningful_count < self.min_messages:
            return (
                False,
                f"Apenas {meaningful_count} mensagens significativas (mín: {self.min_messages})",
            )

        if not current_profile or not current_profile.worldview_summary:
            return True, "Primeiro perfil sendo criado"

        return True, (
            f"Perfil elegível para atualização ({meaningful_count} mensagens significativas)"
        )

    def get_participation_stats_dataframe(
        self,
        member_id: str,
        df: pl.DataFrame,
    ) -> dict[str, object]:
        """Get comprehensive participation statistics using DataFrame operations."""

        messages_df = self.extract_member_messages_dataframe(member_id, df)

        required_columns = {"message", "timestamp"}
        missing = required_columns.difference(messages_df.columns)
        if missing:
            raise KeyError(f"DataFrame must include columns: {', '.join(sorted(missing))}")

        if messages_df.is_empty():
            return {}

        messages_df = messages_df.with_columns(self._word_count_expression())

        total_messages = messages_df.height
        avg_words_per_message = float(messages_df.get_column("word_count").mean() or 0.0)

        first_message = messages_df.get_column("timestamp").min()
        last_message = messages_df.get_column("timestamp").max()
        activity_span = last_message - first_message

        daily_counts = (
            messages_df.with_columns(pl.col("timestamp").dt.date().alias("day"))
            .group_by("day")
            .agg(pl.len().alias("message_count"))
            .sort("day")
        )

        avg_messages_per_day = float(daily_counts.get_column("message_count").mean() or 0.0)

        if daily_counts.is_empty():
            most_active_day = None
            max_messages_in_day = 0
        else:
            top_day = daily_counts.sort("message_count", descending=True).row(0, named=True)
            most_active_day = top_day.get("day") if isinstance(top_day, dict) else top_day[0]
            max_messages_in_day = daily_counts.get_column("message_count").max()

        return {
            "total_messages": total_messages,
            "avg_words_per_message": avg_words_per_message,
            "first_message": first_message,
            "last_message": last_message,
            "activity_span_days": activity_span.days if hasattr(activity_span, "days") else 0,
            "avg_messages_per_day": avg_messages_per_day,
            "active_days": daily_counts.height,
            "most_active_day": most_active_day,
            "max_messages_in_day": max_messages_in_day,
        }

    @staticmethod
    def _word_count_expression() -> pl.Expr:
        """Return a Polars expression that counts non-empty tokens in ``message``."""

        return (
            pl.col("message")
            .cast(pl.Utf8)
            .fill_null("")
            .str.count_matches(r"\S+")
            .alias("word_count")
        )

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
