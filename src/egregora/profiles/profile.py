"""Data structures representing participant profiles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _format_list(items: Sequence[str]) -> str:
    if not items:
        return "- (sem dados observáveis)"
    return "\n".join(f"- {item}" for item in items)


def _format_mapping(mapping: Mapping[str, Any]) -> str:
    if not mapping:
        return "- (sem dados observáveis)"

    lines: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, list | tuple | set):
            values = ", ".join(str(item) for item in value)
        else:
            values = str(value)
        lines.append(f"- **{key}:** {values}")
    return "\n".join(lines)


@dataclass(slots=True)
class ParticipantProfile:
    """Analytical profile for a group participant."""

    member_id: str
    worldview_summary: str = ""
    core_interests: dict[str, Sequence[str] | str] = field(default_factory=dict)
    thinking_style: str = ""
    values_and_priorities: list[str] = field(default_factory=list)
    expertise_areas: dict[str, Sequence[str] | str] = field(default_factory=dict)
    contribution_style: str = ""
    argument_patterns: list[str] = field(default_factory=list)
    questioning_approach: str = ""
    intellectual_influences: list[str] = field(default_factory=list)
    aligns_with: list[str] = field(default_factory=list)
    debates_with: list[str] = field(default_factory=list)
    recent_shifts: list[str] = field(default_factory=list)
    growing_interests: list[str] = field(default_factory=list)
    interaction_patterns: dict[str, str] = field(default_factory=dict)
    markdown_document: str | None = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    analysis_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the profile into a JSON-friendly dictionary."""

        return {
            "member_id": self.member_id,
            "worldview_summary": self.worldview_summary,
            "core_interests": self.core_interests,
            "thinking_style": self.thinking_style,
            "values_and_priorities": list(self.values_and_priorities),
            "expertise_areas": self.expertise_areas,
            "contribution_style": self.contribution_style,
            "argument_patterns": list(self.argument_patterns),
            "questioning_approach": self.questioning_approach,
            "intellectual_influences": list(self.intellectual_influences),
            "aligns_with": list(self.aligns_with),
            "debates_with": list(self.debates_with),
            "recent_shifts": list(self.recent_shifts),
            "growing_interests": list(self.growing_interests),
            "interaction_patterns": dict(self.interaction_patterns),
            "markdown_document": self.markdown_document,
            "last_updated": self.last_updated.isoformat(),
            "analysis_version": self.analysis_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParticipantProfile:
        """Deserialize a profile from a dictionary."""

        last_updated_raw = data.get("last_updated")
        if isinstance(last_updated_raw, str):
            try:
                last_updated = datetime.fromisoformat(last_updated_raw)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=UTC)
                else:
                    last_updated = last_updated.astimezone(UTC)
            except ValueError:
                last_updated = datetime.now(UTC)
        elif isinstance(last_updated_raw, datetime):
            last_updated = (
                last_updated_raw
                if last_updated_raw.tzinfo
                else last_updated_raw.replace(tzinfo=UTC)
            )
        else:
            last_updated = datetime.now(UTC)

        return cls(
            member_id=str(data.get("member_id")),
            worldview_summary=str(data.get("worldview_summary", "")),
            core_interests=dict(data.get("core_interests", {})),
            thinking_style=str(data.get("thinking_style", "")),
            values_and_priorities=list(data.get("values_and_priorities", [])),
            expertise_areas=dict(data.get("expertise_areas", {})),
            contribution_style=str(data.get("contribution_style", "")),
            argument_patterns=list(data.get("argument_patterns", [])),
            questioning_approach=str(data.get("questioning_approach", "")),
            intellectual_influences=list(data.get("intellectual_influences", [])),
            aligns_with=list(data.get("aligns_with", [])),
            debates_with=list(data.get("debates_with", [])),
            recent_shifts=list(data.get("recent_shifts", [])),
            growing_interests=list(data.get("growing_interests", [])),
            interaction_patterns=dict(data.get("interaction_patterns", {})),
            markdown_document=str(data.get("markdown_document"))
            if data.get("markdown_document")
            else None,
            last_updated=last_updated,
            analysis_version=int(data.get("analysis_version", 0)),
        )

    def to_markdown(self) -> str:
        """Return a human friendly Markdown representation."""

        if self.markdown_document:
            return self.markdown_document

        interests_text = _format_mapping(self.core_interests)
        expertise_text = _format_mapping(self.expertise_areas)
        values_text = _format_list(self.values_and_priorities)
        argument_text = _format_list(self.argument_patterns)
        influences_text = _format_list(self.intellectual_influences)
        shifts_text = _format_list(self.recent_shifts)
        growth_text = _format_list(self.growing_interests)

        participation_timing = self.interaction_patterns.get(
            "participation_timing", "Em observação"
        )
        response_style = self.interaction_patterns.get("response_style", "Em observação")
        influence_on_group = self.interaction_patterns.get("influence_on_group", "Em observação")

        aligns_with = ", ".join(self.aligns_with) if self.aligns_with else "Diversos membros"
        debates_with = ", ".join(self.debates_with) if self.debates_with else "Diversos membros"

        return (
            f"# Perfil Analítico: {self.member_id}\n\n"
            "## 🧠 Visão Geral\n\n"
            f"{self.worldview_summary or 'Em construção.'}\n\n"
            "## 🎯 Áreas de Interesse e Perspectiva\n\n"
            f"{interests_text}\n\n"
            "## 💭 Estilo de Pensamento\n\n"
            f"{self.thinking_style or 'Em observação.'}\n\n"
            "**Padrões de argumentação:**\n"
            f"{argument_text}\n\n"
            "**Abordagem às questões:**\n"
            f"{self.questioning_approach or 'Em observação.'}\n\n"
            "## 🎓 Áreas de Expertise Demonstrada\n\n"
            f"{expertise_text}\n\n"
            "## 💡 Valores e Prioridades Observadas\n\n"
            f"{values_text}\n\n"
            "## 🤝 Forma de Contribuir\n\n"
            f"{self.contribution_style or 'Em observação.'}\n\n"
            "### Dinâmica de Participação\n\n"
            f"**Timing de participação:** {participation_timing}\n\n"
            f"**Estilo de resposta:** {response_style}\n\n"
            f"**Influência no grupo:** {influence_on_group}\n\n"
            f"**Alinha-se com:** {aligns_with}\n\n"
            f"**Debates construtivos com:** {debates_with}\n\n"
            "## 📚 Influências Intelectuais Aparentes\n\n"
            f"{influences_text}\n\n"
            "## 🔄 Evolução Recente\n\n"
            "**Mudanças de perspectiva:**\n"
            f"{shifts_text}\n\n"
            "**Novos interesses emergentes:**\n"
            f"{growth_text}\n\n"
            "---\n"
            f"*Análise gerada pelo Egregora - {self.last_updated.strftime('%Y-%m-%d')}*\n"
            "*Baseada em participação contextualizada nas discussões do grupo*\n"
        )

    def update_timestamp(self) -> None:
        """Refresh the ``last_updated`` timestamp."""

        self.last_updated = datetime.now(UTC)

    def apply_updates(self, **updates: Any) -> None:
        """Utility method to update multiple fields at once."""

        for key, value in updates.items():
            if not hasattr(self, key):
                continue
            setattr(self, key, value)
        self.update_timestamp()
