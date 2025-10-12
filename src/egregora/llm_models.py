"""Typed structures shared across LLM powered operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    topics: list[str] = Field(default_factory=list)
    actions: list[ActionItem] = Field(default_factory=list)

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


__all__ = ["SummaryResponse", "ActionItem"]
