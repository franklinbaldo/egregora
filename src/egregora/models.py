"""Core data models for auto-discovery and virtual groups feature."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from egregora.types import GroupSlug

if TYPE_CHECKING:
    pass


class MergeConfig(BaseModel):
    """Configuration for merging multiple groups into a virtual group."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    name: str
    source_groups: list[GroupSlug] = Field(
        ..., validation_alias=AliasChoices("source_groups", "groups"), min_length=1
    )
    tag_style: Literal["emoji", "brackets", "prefix"] = "emoji"
    group_emojis: dict[GroupSlug, str] = Field(
        default_factory=dict, validation_alias=AliasChoices("group_emojis", "emojis")
    )
    default_emoji: str = "📱"
    model_override: str | None = Field(default=None, validation_alias=AliasChoices("model_override", "model"))

    @field_validator("source_groups", mode="before")
    @classmethod
    def _coerce_source_groups(cls, value: object) -> list[GroupSlug]:
        if isinstance(value, list):
            return [GroupSlug(str(item)) for item in value]
        msg = "source_groups must be provided as a list of strings"
        raise ValueError(msg)

    @field_validator("group_emojis", mode="before")
    @classmethod
    def _coerce_group_emojis(cls, value: object) -> dict[GroupSlug, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            msg = "group_emojis must be a mapping of group slug to emoji"
            raise TypeError(msg)
        return {GroupSlug(str(key)): str(val) for key, val in value.items()}
