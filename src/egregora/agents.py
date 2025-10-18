"""Centralised Pydantic agents for structured LLM interactions."""

from __future__ import annotations

from textwrap import dedent
from typing import Any, Sequence

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent


def _coerce_str_list(values: Sequence[Any] | Any) -> list[str]:
    """Return a sanitised list of non-empty strings."""

    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        candidates = list(values)
    else:
        candidates = [values]

    cleaned: list[str] = []
    for item in candidates:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


class ProfilePlanActionPayload(BaseModel):
    """Single action that an LLM agent can request for a profile."""

    tool: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProfilePlanPayload(BaseModel):
    """Structured response containing all plan actions."""

    actions: list[ProfilePlanActionPayload] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalise_actions(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {"actions": []}

        raw_actions = value.get("actions")
        if not isinstance(raw_actions, Sequence):
            return {"actions": []}

        actions: list[dict[str, Any]] = []
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            tool = str(item.get("tool") or "").strip()
            if not tool:
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                payload = {k: v for k, v in item.items() if k != "tool"}
            actions.append({"tool": tool, "payload": payload})
        return {"actions": actions}


class ProfileDecisionPayload(BaseModel):
    """Structured decision on whether a profile should be updated."""

    should_update: bool = True
    reasoning: str = ""
    participation_highlights: list[str] = Field(default_factory=list)
    interaction_insights: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {}

        data = dict(value)
        data["participation_highlights"] = _coerce_str_list(
            data.get("participation_highlights", [])
        )
        data["interaction_insights"] = _coerce_str_list(data.get("interaction_insights", []))
        reasoning = data.get("reasoning")
        if reasoning is not None:
            data["reasoning"] = str(reasoning).strip()
        return data


class KeywordExtractionPayload(BaseModel):
    """Structured keyword extraction output."""

    keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return {}

        keywords = value.get("keywords")
        if not isinstance(keywords, Sequence):
            return {"keywords": []}

        cleaned = [str(item).strip() for item in keywords if str(item).strip()]
        return {"keywords": cleaned}


PROFILE_PLAN_TOOLS_GUIDE = dedent(
    """
    Ferramentas disponíveis (use quantas precisar, ou nenhuma se não houver ação):
    1. create_profile{markdown: string} — Cria o perfil completo em Markdown.
    2. append_sections{sections: [{heading: string, content: string}]} — Acrescenta conteúdo em headings existentes ou cria novos se necessário.
    3. replace_sections{sections: [{heading: string, content: string}]} — Substitui o conteúdo de headings existentes.
    4. set_summary{summary: string} — Atualiza o resumo principal do perfil.
    5. set_values{values: [string]} — Atualiza a lista de valores e prioridades.
    6. set_argument_patterns{patterns: [string]} — Atualiza a lista de padrões de argumentação.

    Retorne APENAS um JSON válido no formato:
    {
      "actions": [
        {"tool": "create_profile", "payload": {"markdown": "..."}},
        {"tool": "append_sections", "payload": {"sections": [{"heading": "## ...", "content": "..."}]}}
      ]
    }
    """
).strip()

PROFILE_PLAN_INSTRUCTIONS = dedent(
    """
    Analise a conversa e o perfil atual. Decida se precisa criar, editar ou apenas registrar que nenhuma ação é necessária.
    Use somente as ferramentas adequadas. Se optar por não alterar nada, retorne {"actions": []}.
    """
).strip()

PROFILE_PLAN_PROMPT_TEMPLATE = dedent(
    """
    Você é um assistente encarregado de manter perfis analíticos de membros.

    {tools_description}

    {instructions}

    Perfil atual (Markdown):
    ```markdown
    {existing_profile}
    ```

    Trechos recentes:
    {formatted_recent}

    Conversa completa:
    {full_conversation}
    """
).strip()


def build_profile_plan_prompt(
    *,
    existing_profile: str,
    formatted_recent: str,
    full_conversation: str,
) -> str:
    """Return the full prompt used by the profile planning agent."""

    existing = existing_profile if existing_profile.strip() else "(Perfil inexistente)"
    recent = (
        formatted_recent if formatted_recent.strip() else "(Sem conversas recentes registradas.)"
    )
    return PROFILE_PLAN_PROMPT_TEMPLATE.format(
        tools_description=PROFILE_PLAN_TOOLS_GUIDE,
        instructions=PROFILE_PLAN_INSTRUCTIONS,
        existing_profile=existing,
        formatted_recent=recent,
        full_conversation=full_conversation.strip(),
    )


PROFILE_PLAN_AGENT = Agent(output_type=ProfilePlanPayload)
PROFILE_DECISION_AGENT = Agent(output_type=ProfileDecisionPayload)
KEYWORD_EXTRACTION_AGENT = Agent(output_type=KeywordExtractionPayload)


__all__ = [
    "build_profile_plan_prompt",
    "KeywordExtractionPayload",
    "KEYWORD_EXTRACTION_AGENT",
    "ProfileDecisionPayload",
    "PROFILE_DECISION_AGENT",
    "ProfilePlanActionPayload",
    "ProfilePlanPayload",
    "PROFILE_PLAN_AGENT",
]
