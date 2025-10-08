"""Typed structures shared across LLM powered operations."""

from __future__ import annotations

from typing import List

from pydantic import AliasChoices, BaseModel, Field


class ActionItem(BaseModel):
    """Actionable follow-up produced by the LLM."""

    description: str = Field(..., min_length=1)
    owner: str | None = Field(
        default=None,
        description="Responsável sugerido ou participante mencionado na conversa.",
    )
    priority: str | None = Field(
        default=None,
        description="Prioridade ou urgência contextualizada (ex.: alta, moderada).",
    )

    model_config = {
        "extra": "ignore",
    }

    def format_bullet(self) -> str:
        """Return a human friendly bullet representation."""

        owner = f" (@{self.owner})" if self.owner else ""
        priority = f" [{self.priority}]" if self.priority else ""
        return f"{self.description.strip()}{owner}{priority}".strip()


class SummaryResponse(BaseModel):
    """Structured analytics block summarising a conversation."""

    summary: str = Field(..., min_length=1)
    topics: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("topics", "key_points"),
    )
    actions: List[ActionItem] = Field(default_factory=list)
    tone: str | None = Field(
        default=None,
        validation_alias=AliasChoices("tone", "sentiment"),
    )
    relevance: int | None = Field(default=None)

    model_config = {
        "extra": "ignore",
    }

    def sanitized_topics(self) -> list[str]:
        """Return cleaned topics, removing blank entries."""

        topics: list[str] = []
        for topic in self.topics:
            if not isinstance(topic, str):
                continue
            cleaned = topic.strip()
            if cleaned:
                topics.append(cleaned)
        return topics

    def sanitized_tone(self) -> str | None:
        """Return a trimmed tone value or ``None`` when missing."""

        if not isinstance(self.tone, str):
            return None
        cleaned = self.tone.strip()
        return cleaned or None

    def sanitized_relevance(self) -> int | None:
        """Return relevance when within the expected range."""

        if self.relevance is None:
            return None
        try:
            value = int(self.relevance)
        except (TypeError, ValueError):
            return None
        if 1 <= value <= 5:
            return value
        return None

    def sanitized_actions(self) -> list[ActionItem]:
        """Return actions filtered for valid descriptions."""

        valid: list[ActionItem] = []
        for item in self.actions:
            if not isinstance(item, ActionItem):
                continue
            description = item.description.strip()
            if description:
                valid.append(item.model_copy(update={"description": description}))
        return valid


class SystemMessageLabel(BaseModel):
    """Classification result for transcript lines."""

    is_system: bool = False
    is_noise: bool = False
    reason: str = Field(default="", description="Justificativa fornecida pelo modelo.")

    model_config = {
        "extra": "ignore",
    }

    def should_discard(self) -> bool:
        """Return ``True`` when the line should be filtered from prompts."""

        return bool(self.is_system or self.is_noise)

    def sanitized_reason(self) -> str:
        """Return a cleaned up explanation string."""

        return self.reason.strip()


__all__ = ["SummaryResponse", "SystemMessageLabel", "ActionItem"]

