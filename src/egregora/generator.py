from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

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

# Prompt resolution and LLM input assembly live here because the generator is
# the only consumer and keeps the pipeline modules focused on data preparation.

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_DEFAULT_TEMPLATE_FILE = "generator_pt-BR.yaml"
_DEFAULT_TEMPLATE_VALUES = {
    "group_name_label": "NOME DO GRUPO",
    "today_label": "DATA DE HOJE",
    "previous_post_header": "POST DO DIA ANTERIOR (INCLUA COMO CONTEXTO, NÃO COPIE):",
    "previous_post_missing": "POST DO DIA ANTERIOR: NÃO ENCONTRADA",
    "enrichment_header": "CONTEXTOS ENRIQUECIDOS DOS LINKS COMPARTILHADOS:",
    "rag_header": "CONTEXTOS HISTÓRICOS DE POSTS RELEVANTES:",
    "transcript_header_single": "TRANSCRITO BRUTO DO ÚLTIMO DIA (NA ORDEM CRONOLÓGICA POR DIA):",
    "transcript_header_multiple": "TRANSCRITO BRUTO DOS ÚLTIMOS {count} DIAS (NA ORDEM CRONOLÓGICA POR DIA):",
}
_PREVIOUS_POST_START_TOKEN = "<<<POST_ONTEM_INICIO>>>>>"
_PREVIOUS_POST_END_TOKEN = "<<<POST_ONTEM_FIM>>>>>"
_TRANSCRIPT_START_TEMPLATE = "<<<TRANSCRITO_{date}_INICIO>>>>>"
_TRANSCRIPT_END_TEMPLATE = "<<<TRANSCRITO_{date}_FIM>>>>>"


class PromptLoader:
    """Resolve prompt and template assets with optional workspace overrides."""

    def __init__(self, *, overrides_dir: Path | None = None) -> None:
        self._overrides_dir = overrides_dir

    def load_text(self, filename: str) -> str:
        """Return the contents of *filename* trimmed of extraneous whitespace."""

        raw = self._load_raw_text(filename)
        stripped = raw.strip()
        if not stripped:
            raise ValueError(f"Prompt '{filename}' is empty after stripping whitespace")
        return stripped

    def load_yaml(self, filename: str) -> dict[str, Any]:
        """Return a mapping stored in a YAML file. Missing files return ``{}``."""

        raw = self._load_raw_text(filename, allow_missing=True)
        if raw is None:
            return {}
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Prompt template '{filename}' must contain a mapping")
        return {str(key): data[key] for key in data}

    def _load_raw_text(self, filename: str, *, allow_missing: bool = False) -> str | None:
        for path in self._candidate_paths(filename):
            if path.exists():
                content = path.read_text(encoding="utf-8")
                if not content.strip():
                    raise ValueError(f"Prompt file '{path}' is empty")
                return content

        try:
            content = (
                resources.files(__package__)
                .joinpath(f"prompts/{filename}")
                .read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            if allow_missing:
                return None
            raise FileNotFoundError(f"Prompt file '{filename}' is missing.") from None

        if not content.strip():
            raise ValueError(f"Prompt resource '{filename}' is empty")
        return content

    def _candidate_paths(self, filename: str) -> tuple[Path, ...]:
        candidates: list[Path] = []
        if self._overrides_dir:
            candidates.append(self._overrides_dir / filename)
        module_candidate = _PROMPTS_DIR / filename
        if module_candidate.exists():
            candidates.append(module_candidate)
        return tuple(candidates)


@dataclass(frozen=True)
class PromptTemplates:
    """Localized headings used to build the LLM user prompt."""

    group_name_label: str
    today_label: str
    previous_post_header: str
    previous_post_missing: str
    enrichment_header: str
    rag_header: str
    transcript_header_single: str
    transcript_header_multiple: str

    def transcript_header(self, count: int) -> str:
        if count <= 1:
            return self.transcript_header_single
        return self.transcript_header_multiple.format(count=count)


def load_prompt_templates(language: str, loader: PromptLoader) -> PromptTemplates:
    """Load localized prompt templates for *language* with sane fallbacks."""

    values = dict(_DEFAULT_TEMPLATE_VALUES)

    default_data = loader.load_yaml(_DEFAULT_TEMPLATE_FILE)
    values.update(_normalize_template_values(default_data))

    for filename in _template_filename_variants(language):
        data = loader.load_yaml(filename)
        if data:
            values.update(_normalize_template_values(data))
            break

    missing_keys = [key for key in _DEFAULT_TEMPLATE_VALUES if key not in values]
    if missing_keys:
        raise ValueError(
            f"Template definition missing required keys: {', '.join(sorted(missing_keys))}"
        )

    return PromptTemplates(**values)


def _normalize_template_values(data: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in data.items():
        if key in _DEFAULT_TEMPLATE_VALUES:
            result[key] = str(value)
    return result


def _template_filename_variants(language: str) -> tuple[str, ...]:
    cleaned = (language or "").strip()
    if not cleaned:
        return ()

    variants = [
        f"generator_{cleaned}.yaml",
        f"generator_{cleaned.replace('-', '_')}.yaml",
        f"generator_{cleaned.lower()}.yaml",
        f"generator_{cleaned.lower().replace('-', '_')}.yaml",
    ]

    seen: dict[str, None] = {}
    for candidate in variants:
        if candidate == _DEFAULT_TEMPLATE_FILE:
            continue
        seen.setdefault(candidate, None)
    return tuple(seen.keys())


class LLMInputBuilder:
    """Compose the user-facing prompt sent to Gemini."""

    def __init__(self, templates: PromptTemplates, timezone: tzinfo) -> None:
        self.templates = templates
        self.timezone = timezone

    def build(
        self,
        *,
        context: PostContext,
        transcripts: Sequence[tuple[date, str]],
    ) -> str:
        sections: list[str] = []
        sections.extend(self._build_metadata_sections(context))
        sections.extend(self._build_previous_post_section(context))
        sections.extend(
            self._build_optional_section(
                self.templates.enrichment_header, context.enrichment_section
            )
        )
        sections.extend(
            self._build_optional_section(self.templates.rag_header, context.rag_context)
        )
        sections.extend(self._build_transcript_section(transcripts))
        return "\n\n".join(sections)

    def _build_metadata_sections(self, context: PostContext) -> list[str]:
        today_str = datetime.now(self.timezone).date().isoformat()
        return [
            f"{self.templates.group_name_label}: {context.group_name}",
            f"{self.templates.today_label}: {today_str}",
        ]

    def _build_previous_post_section(self, context: PostContext) -> list[str]:
        if not context.previous_post:
            return [self.templates.previous_post_missing]
        previous = context.previous_post.strip()
        if not previous:
            return [self.templates.previous_post_missing]
        return [
            self.templates.previous_post_header,
            _PREVIOUS_POST_START_TOKEN,
            previous,
            _PREVIOUS_POST_END_TOKEN,
        ]

    def _build_optional_section(self, heading: str, content: str | None) -> list[str]:
        if not content:
            return []
        stripped = content.strip()
        if not stripped:
            return []
        return [heading, stripped]

    def _build_transcript_section(self, transcripts: Sequence[tuple[date, str]]) -> list[str]:
        header = self.templates.transcript_header(len(transcripts))
        entries: list[str] = [header]
        for transcript_date, transcript_text in transcripts:
            content = transcript_text.strip() if transcript_text else "(vazio)"
            if not content:
                content = "(vazio)"
            entries.extend(
                [
                    _TRANSCRIPT_START_TEMPLATE.format(date=transcript_date.isoformat()),
                    content,
                    _TRANSCRIPT_END_TEMPLATE.format(date=transcript_date.isoformat()),
                ]
            )
        return entries


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
        self._prompt_loader = PromptLoader(overrides_dir=config.prompts_dir)
        self._templates = load_prompt_templates(config.post_language, self._prompt_loader)
        self._input_builder = LLMInputBuilder(self._templates, config.timezone)

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
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Defina GEMINI_API_KEY no ambiente.")
        return genai.Client(api_key=api_key)

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
        base_prompt = self._prompt_loader.load_text(_BASE_PROMPT_NAME)
        if has_group_tags:
            try:
                multigroup_prompt = self._prompt_loader.load_text(_MULTIGROUP_PROMPT_NAME)
                prompt_text = f"{base_prompt}\n\n{multigroup_prompt}"
            except FileNotFoundError:
                # Fallback to base prompt if multigroup prompt is missing
                logger.warning(
                    f"Multigroup prompt file '{_MULTIGROUP_PROMPT_NAME}' not found, using base prompt only"
                )
                prompt_text = base_prompt
        else:
            prompt_text = base_prompt
        return [types.Part.from_text(text=prompt_text)]

    def _build_llm_input(
        self,
        context: PostContext,
        transcripts: Sequence[tuple[date, str]],
    ) -> str:
        """Compose the user prompt sent to Gemini."""

        return self._input_builder.build(context=context, transcripts=transcripts)

    def generate(self, source: GroupSource, context: PostContext) -> str:
        """Generate post for a specific date."""
        transcripts = self._prepare_transcripts(context)
        llm_input = self._build_llm_input(context, transcripts)
        system_instruction = self._build_system_instruction(has_group_tags=source.is_virtual)
        model = self._select_model(source)
        contents = self._build_contents(llm_input)
        safety_settings = self._build_safety_settings()
        generation_config = self._build_generation_config(system_instruction, safety_settings)
        return self._execute_generation(model, contents, generation_config)

    def _prepare_transcripts(self, context: PostContext) -> Sequence[tuple[date, str]]:
        return [(context.target_date, context.transcript)]

    def _select_model(self, source: GroupSource) -> str:
        if source.is_virtual and source.merge_config and source.merge_config.model_override:
            return source.merge_config.model_override
        return self.config.model

    def _build_contents(self, llm_input: str) -> list[types.Content]:
        self._require_google_dependency()
        return [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=llm_input)],
            )
        ]

    def _build_safety_settings(self) -> list[types.SafetySetting]:
        self._require_google_dependency()
        return [
            types.SafetySetting(category=category, threshold=self.config.llm.safety_threshold)
            for category in self.config.llm.safety_categories
        ]

    def _build_generation_config(
        self,
        system_instruction: list[types.Part],
        safety_settings: list[types.SafetySetting],
    ) -> types.GenerateContentConfig:
        self._require_google_dependency()
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=self.config.llm.thinking_budget),
            safety_settings=safety_settings,
            system_instruction=system_instruction,
            response_mime_type="text/plain",
        )

    def _execute_generation(
        self,
        model: str,
        contents: Sequence[types.Content],
        config: types.GenerateContentConfig,
    ) -> str:
        try:
            response = asyncio.run(
                self.gemini_manager.generate_content(
                    subsystem="post_generation",
                    model=model,
                    contents=contents,
                    config=config,
                )
            )
        except GeminiQuotaError as exc:
            raise RuntimeError(
                f"⚠️ Quota de API do Gemini esgotada durante geração de post. "
                f"Tente novamente mais tarde ou ajuste as configurações. Detalhes: {exc}"
            ) from exc

        return response.text.strip() if getattr(response, "text", None) else ""
