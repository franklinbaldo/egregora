"""Logic for determining when and how to update participant profiles."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Callable

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import errors as genai_errors  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows importing without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    genai_errors = None  # type: ignore[assignment]

import polars as pl
from pydantic import ValidationError

from ..agents import (
    PROFILE_DECISION_AGENT,
    PROFILE_PLAN_AGENT,
    build_profile_plan_prompt,
)
from ..markdown_utils import format_markdown
from .profile import ParticipantProfile
from .prompts import UPDATE_DECISION_PROMPT


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


def _display_member_id(member_id: str) -> str:
    segment = member_id.split("-")[0].strip()
    return segment.upper() if segment else member_id


def _extract_member_messages_from_text(member_id: str, conversation: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(member_id)}\s*:\s*(.*)")
    messages: list[str] = []
    for line in conversation.splitlines():
        match = pattern.search(line)
        if match:
            messages.append(match.group(1).strip())
    return messages


def _is_meaningful_message(message: str, min_words: int) -> bool:
    words = [chunk for chunk in re.split(r"\s+", message.strip()) if chunk]
    return len(words) >= min_words


def _format_recent_conversations(conversations: Sequence[str]) -> str:
    if not conversations:
        return "(Sem conversas recentes registradas.)"

    formatted: list[str] = []
    start_index = max(len(conversations) - 5, 0)
    for idx, conv in enumerate(conversations[start_index:], start=1):
        formatted.append(f"## Sessão {idx}\n{conv.strip()}\n")
    return "\n".join(formatted)


def _merge_lists(base: Sequence[str], additions: Sequence[str]) -> list[str]:
    merged: list[str] = []
    for item in base:
        normalized = str(item).strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    for item in additions:
        normalized = str(item).strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def _apply_updates_to_markdown(markdown: str, updates: Sequence[tuple[str, str]]) -> str:
    if not updates:
        return markdown

    lines = markdown.splitlines()

    for heading, addition in updates:
        heading_clean = heading.strip()
        addition_text = addition.strip()
        if not heading_clean or not addition_text:
            continue

        addition_lines = addition_text.splitlines()

        try:
            heading_index = next(
                idx for idx, line in enumerate(lines) if line.strip() == heading_clean
            )
        except StopIteration:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(heading_clean)
            lines.append("")
            heading_index = len(lines) - 2

        insert_pos = heading_index + 1
        while insert_pos < len(lines) and not lines[insert_pos].startswith("#"):
            insert_pos += 1

        block: list[str] = addition_lines
        if insert_pos > 0 and lines[insert_pos - 1].strip():
            block = [""] + block
        if block and block[-1].strip():
            block = block + [""]

        lines[insert_pos:insert_pos] = block

    result = "\n".join(lines).rstrip() + "\n"
    return result


def _replace_section_in_markdown(markdown: str, heading: str, content: str) -> str:
    lines = markdown.splitlines()
    heading_clean = heading.strip()
    content_lines = content.strip().splitlines()

    try:
        heading_index = next(idx for idx, line in enumerate(lines) if line.strip() == heading_clean)
    except StopIteration:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(heading_clean)
        lines.append("")
        heading_index = len(lines) - 2

    end_index = heading_index + 1
    while end_index < len(lines) and not lines[end_index].startswith("#"):
        end_index += 1

    block: list[str] = content_lines or [""]
    if block and block[-1].strip():
        block = block + [""]

    lines[heading_index + 1 : end_index] = block
    return "\n".join(lines).rstrip() + "\n"


@dataclass(slots=True)
class ProfileDraft:
    """Mutable view of a participant profile while agent tools run."""

    markdown: str
    summary: str
    values: list[str]
    arguments: list[str]
    changed: bool = False


def tool_create_profile(draft: ProfileDraft, payload: Mapping[str, object]) -> None:
    markdown = format_markdown(str(payload.get("markdown", "") or ""))
    if not markdown:
        return

    summary = _extract_summary_from_markdown(markdown)
    draft.markdown = markdown
    if summary:
        draft.summary = summary
    draft.changed = True


def tool_append_sections(draft: ProfileDraft, payload: Mapping[str, object]) -> None:
    sections = payload.get("sections")
    if not isinstance(sections, Sequence):
        return

    updates: list[tuple[str, str]] = []
    for item in sections:
        if isinstance(item, Mapping):
            heading = str(item.get("heading", "") or "").strip()
            content = str(item.get("content", "") or "").strip()
            if heading and content:
                updates.append((heading, content))

    if not updates:
        return

    updated = format_markdown(_apply_updates_to_markdown(draft.markdown, updates))
    if updated != draft.markdown:
        draft.markdown = updated
        draft.changed = True


def tool_replace_sections(draft: ProfileDraft, payload: Mapping[str, object]) -> None:
    sections = payload.get("sections")
    if not isinstance(sections, Sequence):
        return

    new_markdown = draft.markdown
    for item in sections:
        if isinstance(item, Mapping):
            heading = str(item.get("heading", "") or "").strip()
            content = str(item.get("content", "") or "").strip()
            if heading and content:
                new_markdown = format_markdown(
                    _replace_section_in_markdown(new_markdown, heading, content)
                )

    if new_markdown != draft.markdown:
        draft.markdown = new_markdown
        draft.changed = True


def tool_set_summary(draft: ProfileDraft, payload: Mapping[str, object]) -> None:
    summary_candidate = str(payload.get("summary", "") or "").strip()
    if summary_candidate and summary_candidate != draft.summary:
        draft.summary = summary_candidate
        draft.changed = True


def tool_set_values(draft: ProfileDraft, payload: Mapping[str, object]) -> None:
    merged = _merge_lists(draft.values, _ensure_str_list(payload.get("values")))
    if merged != draft.values:
        draft.values = merged
        draft.changed = True


def tool_set_argument_patterns(draft: ProfileDraft, payload: Mapping[str, object]) -> None:
    merged = _merge_lists(draft.arguments, _ensure_str_list(payload.get("patterns")))
    if merged != draft.arguments:
        draft.arguments = merged
        draft.changed = True


PROFILE_ACTION_TOOLS: dict[str, Callable[[ProfileDraft, Mapping[str, object]], None]] = {
    "create_profile": tool_create_profile,
    "append_sections": tool_append_sections,
    "replace_sections": tool_replace_sections,
    "set_summary": tool_set_summary,
    "set_values": tool_set_values,
    "set_argument_patterns": tool_set_argument_patterns,
}


def _extract_retry_delay(exc: Exception) -> float | None:
    if genai_errors is not None and isinstance(exc, genai_errors.ResourceExhausted):
        message = str(exc)
        match = re.search(r"retryDelay[\"']?\s*[:=]\s*'?(\d+)(?:\.(\d+))?s", message)
        if match:
            whole = match.group(1)
            frac = match.group(2) or ""
            return float(f"{whole}.{frac}" if frac else whole)

        match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message)
        if match:
            return float(match.group(1))
    return None


def _word_count_expression() -> pl.Expr:
    return (
        pl.col("message").cast(pl.Utf8).fill_null("").str.count_matches(r"\S+").alias("word_count")
    )


@dataclass(slots=True)
class AgentProfileAction:
    tool: str
    payload: dict[str, object]


@dataclass(slots=True)
class ProfileAgentContext:
    current_markdown: str | None
    full_conversation: str
    recent_conversations: Sequence[str]


@dataclass(slots=True)
class ProfileLLMClient:
    max_api_retries: int
    minimum_retry_seconds: float

    async def generate(
        self,
        client: genai.Client,
        *,
        model: str,
        prompt: str,
        temperature: float,
        response_mime_type: str | None = None,
    ):
        if genai is None or types is None:
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada ou o cliente não foi inicializado."
            )
        if client is None:
            raise RuntimeError("Gemini client não foi inicializado.")

        attempt = 0
        last_exc: Exception | None = None
        retries = max(self.max_api_retries, 1)

        while attempt < retries:
            attempt += 1
            try:
                config_kwargs = {"temperature": temperature}
                if response_mime_type:
                    config_kwargs["response_mime_type"] = response_mime_type
                config = types.GenerateContentConfig(**config_kwargs)  # type: ignore[call-arg]
                return await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config=config,
                )
            except Exception as exc:  # pragma: no cover - depends on API errors
                last_exc = exc
                delay = _extract_retry_delay(exc)
                if delay is None or attempt >= retries:
                    break
                await asyncio.sleep(max(delay, self.minimum_retry_seconds))

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Falha desconhecida ao chamar o modelo Gemini.")


@dataclass(slots=True)
class AgentProfiler:
    model: str
    llm: ProfileLLMClient

    async def plan(
        self, client: genai.Client, context: ProfileAgentContext
    ) -> list[AgentProfileAction]:
        existing_profile = context.current_markdown or "(Perfil inexistente)"
        recent = _format_recent_conversations(context.recent_conversations)
        prompt = build_profile_plan_prompt(
            existing_profile=existing_profile,
            formatted_recent=recent,
            full_conversation=context.full_conversation,
        )
        response = await self.llm.generate(
            client,
            model=self.model,
            prompt=prompt,
            temperature=0.5,
            response_mime_type="application/json",
        )

        raw_text = getattr(response, "text", "") or ""
        if not raw_text and getattr(response, "candidates", None):  # pragma: no cover - defensive
            parts = response.candidates[0].content.parts  # type: ignore[attr-defined]
            raw_text = "".join(getattr(part, "text", "") or "" for part in parts)

        if not raw_text:
            raise ValueError("Resposta vazia do modelo ao planejar atualização de perfil.")

        try:
            payload = PROFILE_PLAN_AGENT.output_type.model_validate_json(raw_text)
        except ValidationError as exc:
            raise ValueError(
                "Resposta fora do formato esperado ao planejar atualização de perfil."
            ) from exc

        return [
            AgentProfileAction(tool=action.tool, payload=action.payload)
            for action in payload.actions
        ]


@dataclass(slots=True)
class ProfileUpdater:
    """High level orchestrator that talks to an agent to maintain profiles."""

    min_messages: int = 2
    min_words_per_message: int = 15
    decision_model: str = "models/gemini-flash-latest"
    rewrite_model: str = "models/gemini-flash-latest"
    max_api_retries: int = 3
    minimum_retry_seconds: float = 30.0

    def __post_init__(self) -> None:
        self._llm = ProfileLLMClient(
            max_api_retries=self.max_api_retries,
            minimum_retry_seconds=self.minimum_retry_seconds,
        )
        self._agent = AgentProfiler(model=self.rewrite_model, llm=self._llm)

    async def update_profile_with_agent(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        full_conversation: str,
        recent_conversations: Sequence[str],
        gemini_client: genai.Client,
    ) -> ParticipantProfile | None:
        actions = await self._agent.plan(
            gemini_client,
            context=ProfileAgentContext(
                current_markdown=current_profile.to_markdown() if current_profile else None,
                full_conversation=full_conversation,
                recent_conversations=recent_conversations,
            ),
        )
        return self._apply_actions(member_id, current_profile, actions)

    async def should_update_profile(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        full_conversation: str,
        gemini_client: genai.Client,
    ) -> tuple[bool, str, list[str], list[str]]:
        messages = _extract_member_messages_from_text(member_id, full_conversation)
        meaningful = [
            msg for msg in messages if _is_meaningful_message(msg, self.min_words_per_message)
        ]
        if len(meaningful) < self.min_messages:
            return False, "Participação mínima hoje", [], []
        if not current_profile or not current_profile.worldview_summary:
            return True, "Primeiro perfil sendo criado", [], []

        highlight_prompt = UPDATE_DECISION_PROMPT.format(
            member_id="(omit)",
            member_display=_display_member_id(member_id),
            current_profile=current_profile.to_markdown(),
            full_conversation=full_conversation,
        )
        response = await self._llm.generate(
            gemini_client,
            model=self.decision_model,
            prompt=highlight_prompt,
            temperature=0.3,
            response_mime_type="application/json",
        )
        raw = getattr(response, "text", "") or ""
        if not raw:
            return True, "Perfil elegível para atualização", [], []
        try:
            payload = PROFILE_DECISION_AGENT.output_type.model_validate_json(raw)
        except ValidationError:
            return True, "Perfil elegível para atualização", [], []

        return (
            payload.should_update,
            payload.reasoning,
            payload.participation_highlights,
            payload.interaction_insights,
        )

    def _apply_actions(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        actions: Sequence[AgentProfileAction],
    ) -> ParticipantProfile | None:
        if not actions:
            return current_profile

        draft = ProfileDraft(
            markdown=current_profile.to_markdown() if current_profile else "",
            summary=current_profile.worldview_summary if current_profile else "",
            values=list(current_profile.values_and_priorities) if current_profile else [],
            arguments=list(current_profile.argument_patterns) if current_profile else [],
        )

        for action in actions:
            handler = PROFILE_ACTION_TOOLS.get(action.tool.lower())
            if handler is None:
                continue
            payload: Mapping[str, object]
            if isinstance(action.payload, Mapping):
                payload = action.payload
            else:
                payload = {}
            handler(draft, payload)

        if not draft.changed:
            return current_profile

        analysis_version = (current_profile.analysis_version if current_profile else 0) + 1

        if current_profile is None:
            profile = ParticipantProfile(
                member_id=member_id,
                worldview_summary=draft.summary or "Resumo não fornecido.",
                values_and_priorities=draft.values,
                argument_patterns=draft.arguments,
                markdown_document=draft.markdown,
                analysis_version=analysis_version,
            )
        else:
            profile = replace(
                current_profile,
                worldview_summary=draft.summary or current_profile.worldview_summary,
                values_and_priorities=draft.values
                if draft.values
                else list(current_profile.values_and_priorities),
                argument_patterns=draft.arguments
                if draft.arguments
                else list(current_profile.argument_patterns),
                markdown_document=draft.markdown or current_profile.markdown_document,
                analysis_version=analysis_version,
            )
        profile.update_timestamp()
        return profile

    def extract_member_messages_dataframe(
        self,
        member_id: str,
        df: pl.DataFrame,
    ) -> pl.DataFrame:
        if "author" not in df.columns:
            raise KeyError("DataFrame must have 'author' column")
        return df.filter(pl.col("author") == member_id)

    def should_update_profile_dataframe(
        self,
        member_id: str,
        current_profile: ParticipantProfile | None,
        df: pl.DataFrame,
    ) -> tuple[bool, str]:
        messages_df = self.extract_member_messages_dataframe(member_id, df)
        if "message" not in messages_df.columns:
            raise KeyError("DataFrame deve conter coluna 'message'")
        if messages_df.is_empty():
            return False, "Nenhuma mensagem encontrada"

        messages_with_counts = messages_df.with_columns(_word_count_expression())
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
        messages_df = self.extract_member_messages_dataframe(member_id, df)
        required_columns = {"message", "timestamp"}
        missing = required_columns.difference(messages_df.columns)
        if missing:
            raise KeyError(f"DataFrame must include columns: {', '.join(sorted(missing))}")
        if messages_df.is_empty():
            return {}

        messages_df = messages_df.with_columns(_word_count_expression())

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

    def _extract_member_messages(self, member_id: str, conversation: str) -> list[str]:
        return _extract_member_messages_from_text(member_id, conversation)

    def _is_meaningful(self, message: str) -> bool:
        return _is_meaningful_message(message, self.min_words_per_message)
