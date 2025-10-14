from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from fastmcp import Client as FastMCPClient
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    genai = None
    types = None

from ..gemini_manager import GeminiManager, GeminiQuotaError
from ..pipeline import (
    _format_transcript_section_header,
    _load_prompt,
    _prepare_transcripts,
    _prepare_transcripts_sample,
    build_llm_input,
)

if TYPE_CHECKING:
    from ..config import PipelineConfig
    from ..models import GroupSource

    if genai:
        from google.generativeai.client import Client as GeminiClient


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PostContext:
    """All data required to generate a post."""

    group_name: str
    transcript: str
    target_date: date
    previous_post: str | None = None
    enrichment_section: str | None = None
    rag_context: str | None = None
    rag_query: str | None = None


@dataclass(slots=True)
class RAGSearchResult:
    """Structured payload returned by a RAG client."""

    snippets: list[str]
    records: list[dict[str, Any]]


class RAGClient(Protocol):
    """Protocol implemented by FastMCP-compatible RAG clients."""

    def search(
        self,
        query: str,
        *,
        top_k: int,
        min_similarity: float | None = None,
    ) -> RAGSearchResult: ...


class PromptRenderer:
    """Render user prompts via Jinja templates with contextual sections."""

    def __init__(
        self,
        *,
        template_path: Path | None = None,
        template_name: str = "daily_post_prompt.jinja",
    ) -> None:
        if template_path is not None:
            loader = FileSystemLoader(str(template_path.parent))
            template = template_path.name
        else:
            package_dir = resources.files("egregora.generate.templates")
            loader = FileSystemLoader(str(package_dir))
            template = template_name

        self._environment = Environment(
            loader=loader,
            autoescape=select_autoescape(enabled_extensions=(".jinja",)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        try:
            self._template = self._environment.get_template(template)
        except TemplateNotFound as exc:  # pragma: no cover - invalid user configuration
            raise FileNotFoundError(
                f"Modelo Jinja '{template}' não encontrado em {loader.searchpath}."
            ) from exc

    def render(
        self,
        *,
        group_name: str,
        today: date,
        transcripts: Sequence[tuple[date, str]],
        previous_post: str | None,
        enrichment_section: str | None,
        rag_snippets: Sequence[str],
        rag_records: Sequence[dict[str, Any]],
    ) -> str:
        transcript_header = _format_transcript_section_header(len(transcripts))
        transcript_blocks = [
            {
                "marker": transcript_date.isoformat(),
                "text": (text or "").strip() or "(vazio)",
            }
            for transcript_date, text in transcripts
        ]

        context = {
            "group_name": group_name,
            "today": today.isoformat(),
            "transcripts": transcript_blocks,
            "transcript_header": transcript_header,
            "previous_post": previous_post.strip() if previous_post else None,
            "enrichment_section": enrichment_section.strip() if enrichment_section else None,
            "rag_snippets": [str(snippet).strip() for snippet in rag_snippets if str(snippet).strip()],
            "rag_records": list(rag_records),
        }

        return self._template.render(**context)


class FastMCPContextClient:
    """Small helper that queries a FastMCP RAG server for similar snippets."""

    def __init__(
        self,
        endpoint: str,
        *,
        tool_name: str = "search_similar",
        timeout: float = 30.0,
        client_cls: type[FastMCPClient] | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._tool_name = tool_name
        self._timeout = timeout
        self._client_cls = client_cls or FastMCPClient

    def search(
        self,
        query: str,
        *,
        top_k: int,
        min_similarity: float | None = None,
    ) -> RAGSearchResult:
        payload = {
            "query": query,
            "k": max(int(top_k), 1),
        }
        if min_similarity is not None:
            payload["min_similarity"] = float(min_similarity)

        async def _runner() -> RAGSearchResult:
            url = self._endpoint
            if not url.endswith("/mcp"):
                url = f"{url}/mcp"

            async with self._client_cls(url, timeout=self._timeout) as client:
                result = await client.call_tool(
                    self._tool_name,
                    payload,
                    timeout=self._timeout,
                )
            return _normalise_tool_result(result)

        return _run_coroutine(_runner())


def _run_coroutine(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:  # pragma: no cover - defensive guard for interactive usage
        return loop.run_until_complete(coro)


def _normalise_tool_result(result: Any) -> RAGSearchResult:
    data = getattr(result, "data", None)
    if is_dataclass(data):
        data = asdict(data)

    if data is None:
        structured = getattr(result, "structured_content", None) or {}
        if structured:
            data = structured
        else:
            content_blocks = getattr(result, "content", []) or []
            snippets = [
                getattr(block, "text", "")
                for block in content_blocks
                if getattr(block, "text", "")
            ]
            return RAGSearchResult(snippets=snippets, records=[])

    if is_dataclass(data):
        data = asdict(data)

    if isinstance(data, list):
        return RAGSearchResult(snippets=[str(item) for item in data], records=[])

    if isinstance(data, dict):
        snippets = data.get("snippets") or []
        records = data.get("results") or []

        snippet_list = [str(item) for item in snippets] if isinstance(snippets, list) else []

        if not snippet_list and isinstance(records, list) and records:
            first = records[0]
            if isinstance(first, dict):
                candidate_keys = [
                    key
                    for key, value in first.items()
                    if key not in {"similarity", "vector"} and isinstance(value, str)
                ]
                if candidate_keys:
                    key = candidate_keys[0]
                    snippet_list = [
                        str(record.get(key, ""))
                        for record in records
                        if isinstance(record, dict)
                    ]

        record_list = [
            {str(key): value for key, value in record.items()}
            for record in records
            if isinstance(record, dict)
        ]

        return RAGSearchResult(snippets=snippet_list, records=record_list)

    return RAGSearchResult(snippets=[], records=[])


_BASE_PROMPT_NAME = "system_instruction_base.md"
_MULTIGROUP_PROMPT_NAME = "system_instruction_multigroup.md"


class PostGenerator:
    """Generates posts using an LLM with rate limiting and retry logic."""

    def __init__(
        self,
        config: PipelineConfig,
        *,
        gemini_manager: GeminiManager | None = None,
        llm_client: GeminiClient | None = None,
        prompt_renderer: PromptRenderer | None = None,
        rag_client: RAGClient | None = None,
    ) -> None:
        self.config = config
        self._client = llm_client
        self._gemini_manager = gemini_manager
        self._prompt_renderer = prompt_renderer or PromptRenderer()
        self._rag_client = rag_client

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
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Defina GEMINI_API_KEY ou GOOGLE_API_KEY no ambiente.")
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

    def _render_llm_input(
        self,
        context: PostContext,
        anonymized_transcripts: Sequence[tuple[date, str]],
        rag_result: RAGSearchResult,
    ) -> str:
        today = datetime.now(self.config.timezone).date()
        combined_snippets = list(rag_result.snippets)
        if context.rag_context:
            combined_snippets.insert(0, context.rag_context)

        return self._prompt_renderer.render(
            group_name=context.group_name,
            today=today,
            transcripts=anonymized_transcripts,
            previous_post=context.previous_post,
            enrichment_section=context.enrichment_section,
            rag_snippets=combined_snippets,
            rag_records=rag_result.records,
        )

    def _select_rag_query(
        self,
        context: PostContext,
        anonymized_transcripts: Sequence[tuple[date, str]],
    ) -> str:
        if context.rag_query:
            return context.rag_query.strip()

        sample = _prepare_transcripts_sample(
            anonymized_transcripts,
            max_chars=self.config.rag.max_context_chars,
        )
        return sample.strip()

    def _query_rag(
        self,
        context: PostContext,
        anonymized_transcripts: Sequence[tuple[date, str]],
    ) -> RAGSearchResult:
        if self._rag_client is None or not self.config.rag.enabled:
            return RAGSearchResult(snippets=[], records=[])

        query = self._select_rag_query(context, anonymized_transcripts)
        if not query:
            return RAGSearchResult(snippets=[], records=[])

        try:
            return self._rag_client.search(
                query,
                top_k=self.config.rag.top_k,
                min_similarity=self.config.rag.min_similarity,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            LOGGER.warning("Falha ao consultar FastMCP RAG: %s", exc, exc_info=LOGGER.isEnabledFor(logging.DEBUG))
            return RAGSearchResult(snippets=[], records=[])

    def generate(self, source: GroupSource, context: PostContext) -> str:
        """Generate post for a specific date."""
        self._require_google_dependency()

        transcripts = [(context.target_date, context.transcript)]
        anonymized_transcripts = _prepare_transcripts(transcripts, self.config)
        rag_result = self._query_rag(context, anonymized_transcripts)

        llm_input = self._render_llm_input(context, anonymized_transcripts, rag_result)

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
            response = asyncio.run(
                self.gemini_manager.generate_content(
                    subsystem="post_generation",
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                )
            )

            if response.text:
                return response.text.strip()
            return ""

        except GeminiQuotaError as exc:
            raise RuntimeError(
                "⚠️ Quota de API do Gemini esgotada durante geração de post. "
                f"Tente novamente mais tarde ou ajuste as configurações. Detalhes: {exc}"
            ) from exc


