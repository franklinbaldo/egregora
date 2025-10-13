from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:
    genai = None
    types = None

from .gemini_manager import GeminiManager, GeminiQuotaError

if TYPE_CHECKING:
    from datetime import tzinfo

    from .config import PipelineConfig
    from .models import GroupSource

    if genai:
        from google.generativeai.client import Client as GeminiClient

# The functions _load_prompt and build_llm_input were moved from the deleted
# pipeline.py module to here, as the generator is their only user.
# The _prepare_transcripts function was removed entirely, as the processor
# now handles transcript preparation before calling the generator.

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt either from the editable folder or the package data."""
    local_prompt_path = _PROMPTS_DIR / filename
    if local_prompt_path.exists():
        text = local_prompt_path.read_text(encoding="utf-8")
        stripped = text.strip()
        if not stripped:
            raise ValueError(f"Prompt file '{local_prompt_path}' is empty")
        return stripped

    try:
        package_text = (
            resources.files(__package__).joinpath(f"prompts/{filename}").read_text(encoding="utf-8")
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Prompt file '{filename}' is missing.") from exc

    stripped = package_text.strip()
    if not stripped:
        raise ValueError(f"Prompt resource '{filename}' is empty")
    return stripped


def _format_transcript_section_header(transcript_count: int) -> str:
    """Return a localized header describing the transcript coverage."""
    if transcript_count <= 1:
        return "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):"
    return f"TRANSCRITO BRUTO DOS ÚLTIMOS {transcript_count} DIAS (NA ORDEM CRONOLÓGICA POR DIA):"


def _build_llm_input_string(  # Renamed from build_llm_input to avoid conflict with method
    *,
    context: PostContext,
    timezone: tzinfo,
    transcripts: Sequence[tuple[date, str]],
) -> str:
    """Compose the user prompt sent to Gemini."""
    today_str = datetime.now(timezone).date().isoformat()
    sections: list[str] = [
        f"NOME DO GRUPO: {context.group_name}",
        f"DATA DE HOJE: {today_str}",
    ]

    if context.previous_post:
        sections.extend(
            [
                "POST DO DIA ANTERIOR (INCLUA COMO CONTEXTO, NÃO COPIE):",
                "<<<POST_ONTEM_INICIO>>>",
                context.previous_post.strip(),
                "<<<POST_ONTEM_FIM>>>",
            ]
        )
    else:
        sections.append("POST DO DIA ANTERIOR: NÃO ENCONTRADA")

    if context.enrichment_section:
        sections.extend(
            [
                "CONTEXTOS ENRIQUECIDOS DOS LINKS COMPARTILHADOS:",
                context.enrichment_section,
            ]
        )

    if context.rag_context:
        sections.extend(
            [
                "CONTEXTOS HISTÓRICOS DE POSTS RELEVANTES:",
                context.rag_context,
            ]
        )

    header = _format_transcript_section_header(len(transcripts))
    sections.append(header)

    for transcript_date, transcript_text in transcripts:
        content = transcript_text.strip()
        sections.extend(
            [
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_INICIO>>>",
                content if content else "(vazio)",
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_FIM>>>",
            ]
        )

    return "\n\n".join(sections)


@dataclass(slots=True)
class PostContext:
    """All data required to generate a post."""

    group_name: str
    transcript: str
    target_date: date
    previous_post: str | None = None
    enrichment_section: str | None = None
    rag_context: str | None = None


_BASE_PROMPT_NAME = "system_instruction_base.md"
_MULTIGROUP_PROMPT_NAME = "system_instruction_multigroup.md"


class PostGenerator:
    """Generates posts using an LLM with rate limiting and retry logic."""

    def __init__(
        self,
        config: PipelineConfig,
        gemini_manager: GeminiManager | None = None,
        llm_client: GeminiClient | None = None,  # For backward compatibility
    ):
        self.config = config
        self._client = llm_client
        self._gemini_manager = gemini_manager

    def _require_google_dependency(self) -> None:
        """Ensure the optional google-genai dependency is available."""
        if genai is None or types is None:
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada. "
                "Instale-a para gerar posts (ex.: `pip install google-genai`)."
            )

    def _create_client(self) -> GeminiClient:
        """Instantiate the Gemini client."""
        self._require_google_dependency()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Defina GEMINI_API_KEY no ambiente.")
        return genai.Client(api_key=key)

    @property
    def gemini_manager(self) -> GeminiManager:
        """Lazy-loaded Gemini manager for rate limiting and retries."""
        if self._gemini_manager is None:
            self._gemini_manager = GeminiManager(
                retry_attempts=3,
                minimum_retry_seconds=30.0,
            )
        return self._gemini_manager

    @property
    def client(self) -> GeminiClient:
        """Lazy-loaded Gemini client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _build_system_instruction(self, has_group_tags: bool = False) -> list[types.Part]:
        """Return the validated system prompt."""
        self._require_google_dependency()
        base_prompt = _load_prompt(_BASE_PROMPT_NAME)
        if has_group_tags:
            multigroup_prompt = _load_prompt(_MULTIGROUP_PROMPT_NAME)
            prompt_text = f"{base_prompt}\n\n{multigroup_prompt}"
        else:
            prompt_text = base_prompt
        return [types.Part.from_text(text=prompt_text)]

    def _build_llm_input(
        self,
        context: PostContext,
        transcripts: Sequence[tuple[date, str]],
    ) -> str:
        """Compose the user prompt sent to Gemini."""

        return _build_llm_input_string(
            context=context,
            timezone=self.config.timezone,
            transcripts=transcripts,
        )

    def generate(self, source: GroupSource, context: PostContext) -> str:
        """Generate post for a specific date."""
        self._require_google_dependency()

        transcripts = [(context.target_date, context.transcript)]
        llm_input = self._build_llm_input(context, transcripts)

        system_instruction = self._build_system_instruction(has_group_tags=source.is_virtual)

        model = (
            source.merge_config.model_override
            if source.is_virtual and source.merge_config and source.merge_config.model_override
            else self.config.model
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=llm_input)],
            ),
        ]

        safety_settings = [
            types.SafetySetting(category=category, threshold=self.config.llm.safety_threshold)
            for category in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=self.config.llm.thinking_budget),
            safety_settings=safety_settings,
            system_instruction=system_instruction,
            response_mime_type="text/plain",
        )

        try:
            # Use GeminiManager for rate limiting and retries
            response = asyncio.run(
                self.gemini_manager.generate_content(
                    subsystem="post_generation",
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                )
            )

            # Extract text from response
            if response.text:
                return response.text.strip()
            else:
                # Handle case where response has no text
                return ""

        except GeminiQuotaError as exc:
            # More graceful handling of quota exhaustion
            raise RuntimeError(
                f"⚠️ Quota de API do Gemini esgotada durante geração de post. "
                f"Tente novamente mais tarde ou ajuste as configurações. Detalhes: {exc}"
            ) from exc
