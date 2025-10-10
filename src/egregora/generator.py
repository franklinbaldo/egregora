from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:
    genai = None
    types = None

from .pipeline import _load_prompt, _prepare_transcripts, build_llm_input

if TYPE_CHECKING:
    from .config import PipelineConfig
    from .models import GroupSource

    if genai:
        from google.generativeai.client import Client as GeminiClient


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
    """Generates posts using an LLM."""

    _client: GeminiClient | None

    def __init__(self, config: PipelineConfig, llm_client: GeminiClient | None = None):
        self.config = config
        self._client = llm_client

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
        anonymized_transcripts: Sequence[tuple[date, str]],
    ) -> str:
        """Compose the user prompt sent to Gemini."""

        return build_llm_input(
            group_name=context.group_name,
            timezone=self.config.timezone,
            transcripts=anonymized_transcripts,
            previous_post=context.previous_post,
            enrichment_section=context.enrichment_section,
            rag_context=context.rag_context,
        )

    def generate(self, source: GroupSource, context: PostContext) -> str:
        """Generate post for a specific date."""
        self._require_google_dependency()

        transcripts = [(context.target_date, context.transcript)]
        anonymized_transcripts = _prepare_transcripts(transcripts, self.config)

        llm_input = self._build_llm_input(context, anonymized_transcripts)

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
