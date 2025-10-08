"""Core data models for auto-discovery and virtual groups feature."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .types import GroupSlug


@dataclass(slots=True)
class WhatsAppExport:
    """Metadata extracted from a WhatsApp ZIP export."""

    zip_path: Path
    group_name: str  # "RC LatAm"
    group_slug: GroupSlug  # "rc-latam"
    export_date: date  # 2025-10-01
    chat_file: str  # "Conversa do WhatsApp com RC LatAm.txt"
    media_files: list[str]  # ["IMG-001.jpg", ...]


class MergeConfig(BaseModel):
    """Configuration for merging multiple groups into a virtual group."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str  # "RC Americas"
    source_groups: list[GroupSlug] = Field(
        ...,
        validation_alias=AliasChoices("source_groups", "groups"),
        min_length=1,
    )
    tag_style: Literal["emoji", "brackets", "prefix"] = "emoji"
    group_emojis: dict[GroupSlug, str] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("group_emojis", "emojis"),
    )
    model_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("model_override", "model"),
    )

    @field_validator("source_groups", mode="before")
    @classmethod
    def _coerce_source_groups(cls, value: object) -> list[GroupSlug]:
        if isinstance(value, list):
            coerced = [GroupSlug(str(item)) for item in value]
            if not coerced:
                msg = "Merge configuration must include at least one source group"
                raise ValueError(msg)
            return coerced
        msg = "source_groups must be provided as a list of strings"
        raise ValueError(msg)

    @field_validator("group_emojis", mode="before")
    @classmethod
    def _coerce_group_emojis(
        cls, value: object
    ) -> dict[GroupSlug, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            msg = "group_emojis must be a mapping of group slug to emoji"
            raise ValueError(msg)
        return {GroupSlug(str(key)): str(val) for key, val in value.items()}


@dataclass(slots=True)
class GroupSource:
    """
    Source for generating posts.
    Can be real (single group) or virtual (merge of multiple groups).
    """

    slug: GroupSlug  # "rc-latam" or "rc-americas"
    name: str  # "RC LatAm" or "RC Americas"
    exports: list[WhatsAppExport]  # Exports for this source
    is_virtual: bool = False
    merge_config: MergeConfig | None = None
