from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:
    genai = None
    types = None

from .pipeline import _prepare_transcripts

if TYPE_CHECKING:
    from .config import PipelineConfig
    from .models import GroupSource

    if genai:
        from google.generativeai.client import Client as GeminiClient


@dataclass(slots=True)
class NewsletterContext:
    """All data required to generate a newsletter."""

    group_name: str
    transcript: str
    target_date: date
    previous_newsletter: str | None = None
    enrichment_section: str | None = None
    rag_context: str | None = None


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_BASE_PROMPT_NAME = "system_instruction_base.md"
_MULTIGROUP_PROMPT_NAME = "system_instruction_multigroup.md"


class NewsletterGenerator:
    """Generates newsletters using an LLM."""

    _client: "GeminiClient | None"

    def __init__(
        self, config: "PipelineConfig", llm_client: "GeminiClient | None" = None
    ):
        self.config = config
        self._client = llm_client

    def _require_google_dependency(self) -> None:
        """Ensure the optional google-genai dependency is available."""
        if genai is None or types is None:
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada. "
                "Instale-a para gerar newsletters (ex.: `pip install google-genai`)."
            )

    def _create_client(self) -> "GeminiClient":
        """Instantiate the Gemini client."""
        self._require_google_dependency()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Defina GEMINI_API_KEY no ambiente.")
        return genai.Client(api_key=key)

    @property
    def client(self) -> "GeminiClient":
        """Lazy-loaded Gemini client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt either from the editable folder or package data."""
        local_prompt_path = _PROMPTS_DIR / filename
        if local_prompt_path.exists():
            text = local_prompt_path.read_text(encoding="utf-8")
            stripped = text.strip()
            if not stripped:
                raise ValueError(f"Prompt file '{local_prompt_path}' is empty")
            return stripped

        # Fallback to package resources if local file doesn't exist
        try:
            package_text = (
                resources.files(__package__)
                .joinpath(f"prompts/{filename}")
                .read_text(encoding="utf-8")
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Prompt file '{filename}' is missing.") from exc

        stripped = package_text.strip()
        if not stripped:
            raise ValueError(f"Prompt resource '{filename}' is empty")
        return stripped

    def _build_system_instruction(
        self, has_group_tags: bool = False
    ) -> list["types.Part"]:
        """Return the validated system prompt."""
        self._require_google_dependency()
        base_prompt = self._load_prompt(_BASE_PROMPT_NAME)
        if has_group_tags:
            multigroup_prompt = self._load_prompt(_MULTIGROUP_PROMPT_NAME)
            prompt_text = f"{base_prompt}\n\n{multigroup_prompt}"
        else:
            prompt_text = base_prompt
        return [types.Part.from_text(text=prompt_text)]

    def _format_transcript_section_header(self, transcript_count: int) -> str:
        """Return a localized header describing how many transcripts are included."""
        if transcript_count <= 1:
            return "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):"
        return (
            f"TRANSCRITO BRUTO DOS ÚLTIMOS {transcript_count} DIAS "
            "(NA ORDEM CRONOLÓGICA POR DIA):"
        )

    def _build_llm_input(
        self,
        context: NewsletterContext,
        anonymized_transcripts: Sequence[tuple[date, str]],
    ) -> str:
        """Compose the user prompt sent to Gemini."""
        today_str = datetime.now(self.config.timezone).date().isoformat()
        sections: list[str] = [
            f"NOME DO GRUPO: {context.group_name}",
            f"DATA DE HOJE: {today_str}",
        ]

        if context.previous_newsletter:
            sections.extend([
                "NEWSLETTER DO DIA ANTERIOR (INCLUA COMO CONTEXTO, NÃO COPIE):",
                "<<<NEWSLETTER_ONTEM_INICIO>>>",
                context.previous_newsletter.strip(),
                "<<<NEWSLETTER_ONTEM_FIM>>>",
            ])
        else:
            sections.append("NEWSLETTER DO DIA ANTERIOR: NÃO ENCONTRADA")

        if context.enrichment_section:
            sections.extend([
                "CONTEXTOS ENRIQUECIDOS DOS LINKS COMPARTILHADOS:",
                context.enrichment_section,
            ])

        if context.rag_context:
            sections.extend([
                "CONTEXTOS HISTÓRICOS DE NEWSLETTERS RELEVANTES:",
                context.rag_context,
            ])

        header = self._format_transcript_section_header(len(anonymized_transcripts))
        sections.append(header)
        for transcript_date, transcript_text in anonymized_transcripts:
            sections.extend([
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_INICIO>>>",
                transcript_text.strip() if transcript_text.strip() else "(vazio)",
                f"<<<TRANSCRITO_{transcript_date.isoformat()}_FIM>>>",
            ])

        return "\n\n".join(sections)

    def generate(self, source: "GroupSource", context: NewsletterContext) -> str:
        """Generate newsletter for a specific date."""
        self._require_google_dependency()

        transcripts = [(context.target_date, context.transcript)]
        anonymized_transcripts = _prepare_transcripts(transcripts, self.config)

        llm_input = self._build_llm_input(context, anonymized_transcripts)

        system_instruction = self._build_system_instruction(
            has_group_tags=source.is_virtual
        )

        model = (
            source.merge_config.model_override
            if source.is_virtual
            and source.merge_config
            and source.merge_config.model_override
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
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.config.llm.thinking_budget
            ),
            safety_settings=safety_settings,
            system_instruction=system_instruction,
        )

        output_lines: list[str] = []
        stream = self.client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        for chunk in stream:
            if chunk.text:
                output_lines.append(chunk.text)

        return "".join(output_lines).strip()