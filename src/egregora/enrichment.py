"""Content enrichment orchestrator using Gemini's native URL support."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import mimetypes
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows the module to load without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import polars as pl
from diskcache import Cache
from pydantic import ValidationError
from pydantic_ai import Agent

from .config import EnrichmentConfig
from .gemini_manager import GeminiQuotaError
from .llm_models import ActionItem, SummaryResponse
from .media_extractor import MediaExtractor
from .schema import ensure_message_schema

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .gemini_manager import GeminiManager
    from .media_extractor import MediaFile

URL_RE = re.compile(r"(https?://[^\s>\)]+)", re.IGNORECASE)
MESSAGE_RE = re.compile(
    r"^(?P<time>\d{1,2}(?:[:hH]\d{2}))\s*[\-–—]\s*(?P<sender>.+?):\s*(?P<message>.*)$"
)
MEDIA_TOKEN_RE = re.compile(r"<m[íi]dia oculta>", re.IGNORECASE)

CACHE_RECORD_VERSION = "2.0"
CACHE_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

SUMMARY_AGENT = Agent(output_type=SummaryResponse)

MEDIA_PLACEHOLDER_SUMMARY = (
    "Não foi possível acessar esta mídia. Use somente o contexto das mensagens para inferir o que ela "
    "pode significar ou ignore-a se estiver pouco claro."
)
MEDIA_PLACEHOLDER_TOPIC = "Mídia sem conteúdo acessível"
PROMPT_TEMPERATURE = 0.2
TOKEN_ESTIMATE_DIVISOR = 4
TOKEN_ESTIMATE_MIN = 1
PASSWORD_HASH_ALGORITHM = "sha256"
REDACTED_PASSWORD_TOKEN = "***"


COLUMN_SEPARATOR = "; "


logger = logging.getLogger(__name__)


def _normalise_url(url: str) -> str:
    parts = urlparse(url)

    scheme = parts.scheme.lower()

    hostname = (parts.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    if hostname and ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    default_port: int | None
    if scheme == "http":
        default_port = 80
    elif scheme == "https":
        default_port = 443
    else:
        default_port = None

    port = parts.port
    if default_port is not None and port == default_port:
        port = None

    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            hasher = hashlib.new(PASSWORD_HASH_ALGORITHM)
            hasher.update(parts.password.encode("utf-8"))
            userinfo += f":{hasher.hexdigest()}"
        userinfo += "@"

    netloc = hostname
    if port is not None and hostname:
        netloc = f"{hostname}:{port}"
    elif port is not None:
        netloc = f":{port}"

    netloc = f"{userinfo}{netloc}" if userinfo or netloc else userinfo

    path = parts.path
    if len(path) > 1:
        path = path.rstrip("/")

    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)

    return urlunparse((scheme, netloc, path, parts.params, query, ""))


def _cache_key_for_url(url: str) -> str:
    normalised = _normalise_url(url)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, normalised))


def _redact_url(url: str) -> str:
    parts = urlparse(url)
    if not (parts.username or parts.password):
        return url

    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    userinfo = parts.username or ""
    if userinfo:
        userinfo = f"{userinfo}:{REDACTED_PASSWORD_TOKEN}@" if parts.password else f"{userinfo}@"

    redacted_netloc = f"{userinfo}{netloc}" if (userinfo or netloc) else netloc
    return urlunparse(
        (parts.scheme, redacted_netloc, parts.path, parts.params, parts.query, parts.fragment)
    )


def _extract_domain(url: str) -> str | None:
    parts = urlparse(url)
    hostname = parts.hostname
    if not hostname and parts.port is None:
        return None
    if parts.port:
        return f"{hostname}:{parts.port}" if hostname else str(parts.port)
    return hostname


def _coerce_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    return None


def _extract_cache_entry(entry: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(entry, dict):
        return None, None

    payload = entry.get("payload")
    if isinstance(payload, dict):
        return payload, entry

    if any(key in entry for key in ("enrichment", "context", "metadata")):
        return entry, {"payload": entry}

    return None, None


@dataclass(slots=True)
class AnalysisResult:
    """Structured information returned by Gemini."""

    summary: str | None
    topics: list[str]
    actions: list[ActionItem]
    relevance: int
    raw_response: str | None
    error: str | None = None

    @property
    def is_successful(self) -> bool:
        return self.error is None


@dataclass(slots=True)
class ContentReference:
    """Represents a link or media mention extracted from transcripts."""

    date: date
    url: str | None
    sender: str | None
    timestamp: str | None
    message: str
    context_before: list[str]
    context_after: list[str]
    is_media_placeholder: bool = False
    media_key: str | None = None
    media_path: Path | None = None
    media_type: str | None = None

    def context_block(self) -> str:
        """Return a human-friendly snippet of the surrounding chat messages."""

        before = " | ".join(self.context_before)
        after = " | ".join(self.context_after)
        return " || ".join(filter(None, [before, self.message, after]))

    def redacted_url(self) -> str | None:
        if not self.url:
            return None
        return _redact_url(self.url)


@dataclass(slots=True)
class EnrichedItem:
    """Container for the enrichment of a single reference."""

    reference: ContentReference
    analysis: AnalysisResult | None
    error: str | None = None

    @property
    def relevance(self) -> int:
        if self.analysis is None:
            return 0
        return self.analysis.relevance


@dataclass(slots=True)
class EnrichmentResult:
    """Aggregated enrichment data used by the prompt builder."""

    items: list[EnrichedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    metrics: EnrichmentRunMetrics | None = None

    def relevant_items(self, threshold: int) -> list[EnrichedItem]:
        return [item for item in self.items if item.relevance >= threshold]

    def format_for_prompt(self, threshold: int) -> str | None:
        """Render a textual section that can be appended to the LLM prompt."""

        relevant = self.relevant_items(threshold)
        if not relevant:
            return None

        lines: list[str] = [
            "CONTEÚDOS COMPARTILHADOS (contexto auxiliar para o modelo):",
            "<<<ENRIQUECIMENTO_INICIO>>>",
        ]
        for index, item in enumerate(relevant, start=1):
            ref = item.reference
            analysis = item.analysis
            lines.append(f"{index}. URL: {ref.redacted_url() or 'Mídia sem link'}")
            if ref.sender or ref.timestamp:
                sender = ref.sender or "(autor desconhecido)"
                when = ref.timestamp or "horário desconhecido"
                lines.append(f"   Remetente: {sender.strip()} às {when} em {ref.date.isoformat()}")
            if analysis and analysis.summary:
                lines.append(f"   Resumo: {analysis.summary}")
            if analysis and analysis.topics:
                lines.append("   Tópicos principais:")
                for point in analysis.topics:
                    lines.append(f"     - {point}")
            if analysis and analysis.actions:
                lines.append("   Ações sugeridas:")
                for action in analysis.actions:
                    lines.append(f"     - {action.format_bullet()}")
            if analysis:
                lines.append(f"   Relevância estimada: {analysis.relevance}/5")
            if ref.context_before or ref.context_after:
                lines.append(f"   Contexto: {ref.context_block()}")
        lines.append("<<<ENRIQUECIMENTO_FIM>>>")
        return "\n".join(lines)


@dataclass(slots=True)
class EnrichmentRunMetrics:
    """Metrics captured for a single enrichment execution."""

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    total_references: int
    analyzed_items: int
    relevant_items: int
    error_count: int
    domains: tuple[str, ...]
    urls: tuple[str, ...]
    threshold: int

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 4),
            "total_references": self.total_references,
            "analyzed_items": self.analyzed_items,
            "relevant_items": self.relevant_items,
            "error_count": self.error_count,
            "domains": list(self.domains),
            "urls": list(self.urls),
            "threshold": self.threshold,
        }

    def to_csv_row(self, errors: Sequence[str]) -> dict[str, object]:
        base = self.to_dict()
        base["domains"] = COLUMN_SEPARATOR.join(self.domains)
        base["urls"] = COLUMN_SEPARATOR.join(self.urls)
        base["errors"] = COLUMN_SEPARATOR.join(errors)
        return base


class ContentEnricher:
    """High-level orchestrator that extracts and analyzes shared links."""

    def __init__(
        self,
        config: EnrichmentConfig,
        *,
        cache: Cache | None = None,
        gemini_manager: GeminiManager | None = None,
        cache_ttl_days: int | None = None,
    ) -> None:
        self._config = config
        self._cache = cache
        self._gemini_manager = gemini_manager
        self._cache_ttl_seconds = (
            max(1, int(cache_ttl_days)) * 24 * 60 * 60 if cache_ttl_days else None
        )
        self._metrics: dict[str, int] = {
            "llm_calls": 0,
            "estimated_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    @property
    def metrics(self) -> dict[str, int]:
        """Return LLM usage metrics for observability."""

        return dict(self._metrics)

    async def enrich_dataframe(
        self,
        df: pl.DataFrame,
        *,
        client: genai.Client | None,
        target_dates: Sequence[date] | None = None,
        media_files: Mapping[str, MediaFile] | None = None,
    ) -> EnrichmentResult:
        """DataFrame-native enrichment pipeline using Polars expressions."""

        start = perf_counter()
        started_at = datetime.now(UTC)
        references: list[ContentReference] = []
        if not self._config.enabled:
            result = EnrichmentResult()
            return self._finalize_result(
                started_at=started_at,
                start=start,
                references=references,
                result=result,
            )

        frame = self._prepare_enrichment_frame(df, target_dates)
        if frame is None:
            result = EnrichmentResult()
            return self._finalize_result(
                started_at=started_at,
                start=start,
                references=references,
                result=result,
            )

        references = self._extract_references_from_frame(frame)
        references = references[: self._config.max_links]

        if not references:
            result = EnrichmentResult()
            return self._finalize_result(
                started_at=started_at,
                start=start,
                references=references,
                result=result,
            )

        result = await self._enrich_references(
            references,
            client=client,
            media_files=media_files,
        )
        return self._finalize_result(
            started_at=started_at,
            start=start,
            references=references,
            result=result,
        )

    # TODO: This function is too long and complex. It should be broken down into
    # smaller functions for better readability and maintenance.
    async def _analyze_reference(  # noqa: PLR0912, PLR0915
        self,
        reference: ContentReference,
        *,
        client: genai.Client | None,
        media_info: MediaFile | None = None,
    ) -> AnalysisResult:
        manager = self._gemini_manager

        if manager is None and (types is None or client is None):
            return AnalysisResult(
                summary=None,
                topics=[],
                actions=[],
                relevance=1,
                raw_response=None,
                error="Cliente Gemini indisponível para análise.",
            )

        prompt = self._build_prompt(reference)
        if reference.media_path:
            prompt += (
                "\n\nUm arquivo de mídia desta conversa foi anexado a você. "
                "Descreva sucintamente o conteúdo da mídia e por que ela é relevante "
                "para a discussão, mencionando participantes ou mensagens importantes."
            )

        parts = [types.Part.from_text(text=prompt)]
        if reference.url:
            try:
                parts.append(types.Part.from_uri(file_uri=reference.url))
            # FIXME: This is a broad exception. It should be more specific, for example,
            # catching exceptions from the `google.genai` library if they exist.
            except Exception:  # pragma: no cover - depends on mimetype detection
                fallback = f"URL compartilhada: {reference.redacted_url()}"
                parts.append(types.Part.from_text(text=fallback))

        media_bytes: bytes | None = None
        media_mime: str | None = None
        if reference.media_path:
            try:
                media_bytes = reference.media_path.read_bytes()
            # FIXME: This is a broad exception. It should be more specific, for example,
            # catching `FileNotFoundError` or `IOError`.
            except Exception as exc:  # pragma: no cover - file issues
                logger.warning("Falha ao ler mídia %s: %s", reference.media_path, exc)
                media_bytes = None

            if media_bytes:
                mime_candidate = mimetypes.guess_type(reference.media_path.name)[0]
                if mime_candidate is None and reference.media_type:
                    if reference.media_type == "image":
                        mime_candidate = "image/jpeg"
                    elif reference.media_type == "video":
                        mime_candidate = "video/mp4"
                    elif reference.media_type == "audio":
                        mime_candidate = "audio/ogg"
                media_mime = mime_candidate or "application/octet-stream"
                try:
                    parts.append(types.Part.from_bytes(data=media_bytes, mime_type=media_mime))
                # FIXME: This is a broad exception. It should be more specific.
                except Exception as exc:  # pragma: no cover - SDK specific
                    logger.warning(
                        "Falha ao anexar mídia '%s' ao prompt: %s",
                        reference.media_path,
                        exc,
                    )

        contents = [types.Content(role="user", parts=parts)]
        afc_config = None
        if types is not None:
            max_remote_calls = self._config.afc_max_remote_calls
            if max_remote_calls is None:
                max_remote_calls = max(self._config.max_links, 10)
            max_remote_calls = max(1, int(max_remote_calls))
            afc_config = types.AutomaticFunctionCallingConfig(maximum_remote_calls=max_remote_calls)
        config_kwargs: dict[str, Any] = {
            "temperature": PROMPT_TEMPERATURE,
            "response_mime_type": "application/json",
        }
        if afc_config is not None:
            config_kwargs["automatic_function_calling"] = afc_config
        config = types.GenerateContentConfig(**config_kwargs)

        try:
            if manager is not None:
                response = await manager.generate_content(
                    "enrichment",
                    model=self._config.enrichment_model,
                    contents=contents,
                    config=config,
                )
            else:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self._config.enrichment_model,
                    contents=contents,
                    config=config,
                )
        except GeminiQuotaError as exc:
            return AnalysisResult(
                summary=None,
                topics=[],
                actions=[],
                relevance=1,
                raw_response=None,
                error=str(exc),
            )
        # FIXME: This is a broad exception. It should be more specific.
        except Exception as exc:  # pragma: no cover - depends on network/model
            return AnalysisResult(
                summary=None,
                topics=[],
                actions=[],
                relevance=1,
                raw_response=None,
                error=str(exc),
            )

        analysis = self._parse_response(response)
        self._record_llm_usage(prompt, analysis.raw_response)
        return analysis

    def _store_in_cache(self, reference: ContentReference, analysis: AnalysisResult) -> None:
        cache = self._cache
        if cache is None or not reference.url:
            return

        enrichment_payload = {
            "summary": analysis.summary,
            "topics": list(analysis.topics),
            "actions": [item.model_dump() for item in analysis.actions],
            "relevance": analysis.relevance,
            "raw_response": analysis.raw_response,
        }
        timestamp = datetime.now(UTC).strftime(CACHE_TIMESTAMP_FORMAT)
        domain = _extract_domain(reference.url) if reference.url else None
        context = {
            "message": reference.message,
            "messages_before": list(reference.context_before),
            "messages_after": list(reference.context_after),
            "sender": reference.sender,
            "timestamp": reference.timestamp,
            "date": reference.date.isoformat(),
        }
        metadata = {
            "domain": domain,
            "extracted_at": timestamp,
        }
        payload: dict[str, Any] = {
            "model": self._config.enrichment_model,
            "analyzed_at": timestamp,
            "enrichment": enrichment_payload,
            "context": context,
            "metadata": {k: v for k, v in metadata.items() if v is not None},
            "version": CACHE_RECORD_VERSION,
        }

        cache_key = _cache_key_for_url(reference.url)
        _, existing_record = _extract_cache_entry(cache.get(cache_key))

        now = datetime.now(UTC)
        first_seen = _coerce_timestamp((existing_record or {}).get("first_seen")) or now
        hit_count = int((existing_record or {}).get("hit_count", 0))

        entry = {
            "payload": payload,
            "first_seen": first_seen,
            "last_used": now,
            "hit_count": hit_count,
        }

        try:
            cache.set(cache_key, entry, expire=self._cache_ttl_seconds)
        except Exception:
            # Cache failures must not break the enrichment flow.
            return

    def _analysis_from_cache(self, payload: dict[str, object]) -> AnalysisResult | None:
        enrichment = payload.get("enrichment")
        if not isinstance(enrichment, dict):
            return None

        summary = self._coerce_string(enrichment.get("summary"))
        topics = [
            point.strip()
            for point in enrichment.get("topics", [])
            if isinstance(point, str) and point.strip()
        ]
        actions: list[ActionItem] = []
        for action_payload in enrichment.get("actions", []) or []:
            try:
                action = ActionItem.model_validate(action_payload)
            except ValidationError:
                continue
            cleaned = action.description.strip()
            if not cleaned:
                continue
            actions.append(action.model_copy(update={"description": cleaned}))
        relevance = enrichment.get("relevance")
        if not isinstance(relevance, int):
            relevance = 1

        raw_response = enrichment.get("raw_response")
        if raw_response is not None and not isinstance(raw_response, str):
            raw_response = str(raw_response)

        return AnalysisResult(
            summary=summary,
            topics=topics,
            actions=actions,
            relevance=relevance,
            raw_response=raw_response,
        )

    @staticmethod
    def _parse_response(response: object) -> AnalysisResult:
        raw_text = getattr(response, "text", None)
        if raw_text is None and getattr(response, "candidates", None):
            parts = response.candidates[0].content.parts  # type: ignore[attr-defined]
            raw_text = "".join(getattr(part, "text", "") or "" for part in parts)

        if raw_text is None:
            return AnalysisResult(
                summary=None,
                topics=[],
                actions=[],
                relevance=1,
                raw_response=None,
                error="Resposta vazia do modelo.",
            )

        raw_text = raw_text.strip()
        payload: SummaryResponse | None = None
        try:
            payload = SUMMARY_AGENT.output_type.model_validate_json(raw_text)
        except ValidationError:
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                try:
                    payload = SUMMARY_AGENT.output_type.model_validate(data)
                except ValidationError:
                    payload = None

        if payload is None:
            summary = ContentEnricher._coerce_string(raw_text)
            return AnalysisResult(
                summary=summary,
                topics=[],
                actions=[],
                relevance=1,
                raw_response=raw_text,
                error="Resposta fora do formato esperado; usando fallback seguro.",
            )

        summary = ContentEnricher._coerce_string(payload.summary)
        topics = payload.sanitized_topics()
        actions = payload.sanitized_actions()
        relevance = ContentEnricher._estimate_relevance(summary, topics, actions)

        return AnalysisResult(
            summary=summary,
            topics=topics,
            actions=actions,
            relevance=relevance,
            raw_response=raw_text,
        )

    def _build_prompt(self, reference: ContentReference) -> str:
        context = {
            "url": reference.url,
            "sender": reference.sender,
            "timestamp": reference.timestamp,
            "date": reference.date.isoformat(),
            "chat_message": reference.message,
            "context_before": reference.context_before,
            "context_after": reference.context_after,
        }
        if reference.media_key:
            context["media_identifier"] = reference.media_key
        if reference.is_media_placeholder:
            context["media_placeholder"] = True
        # TODO: The prompt is hardcoded in Portuguese. It should be moved to a
        # configurable localization file to support multiple languages.
        return (
            "Você analisa conteúdos compartilhados em um grupo de WhatsApp. "
            "Considere o contexto das mensagens e o link anexado. Responda em JSON "
            "com as chaves: summary (string em pt-BR), topics (lista com até 3 temas "
            "relevantes em string) e actions (lista com até 3 objetos contendo os "
            "campos description, owner opcional e priority opcional). Mantenha as "
            "listas vazias quando não houver informações úteis e explique incertezas "
            "no summary. Dados do chat:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _coerce_string(value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    def _record_llm_usage(self, prompt: str, response_text: str | None) -> None:
        self._metrics["llm_calls"] = self._metrics.get("llm_calls", 0) + 1
        estimated = max(
            TOKEN_ESTIMATE_MIN,
            (len(prompt) + len(response_text or "")) // TOKEN_ESTIMATE_DIVISOR,
        )
        self._metrics["estimated_tokens"] = self._metrics.get("estimated_tokens", 0) + estimated

    def _fetch_cache_entry(
        self, url: str | None
    ) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
        cache = self._cache
        if not url or cache is None:
            return None, None, None

        cache_key = _cache_key_for_url(url)
        entry = cache.get(cache_key)
        if entry is None:
            return cache_key, None, None

        payload, record = _extract_cache_entry(entry)
        if payload is None:
            try:
                cache.delete(cache_key)
            except Exception:
                pass
            return cache_key, None, None

        return cache_key, payload, record

    def _register_cache_hit(
        self, cache_key: str, payload: dict[str, Any], record: dict[str, Any] | None
    ) -> None:
        cache = self._cache
        if cache is None:
            return

        entry = record or {"payload": payload}
        entry["payload"] = payload

        now = datetime.now(UTC)
        entry["last_used"] = now
        entry["hit_count"] = int(entry.get("hit_count", 0)) + 1
        entry["first_seen"] = _coerce_timestamp(entry.get("first_seen")) or now

        try:
            cache.set(cache_key, entry, expire=self._cache_ttl_seconds)
        except Exception:
            return

    @staticmethod
    def _estimate_relevance(
        summary: str | None,
        topics: Sequence[str],
        actions: Sequence[ActionItem],
    ) -> int:
        """Derive a lightweight relevance score from structured data."""

        score = 1
        if summary:
            score = max(score, 2)
        if topics:
            score = max(score, 3)
        if actions:
            score = max(score, 5)
        return score

    async def _enrich_references(
        self,
        references: Sequence[ContentReference],
        *,
        client: genai.Client | None,
        media_files: Mapping[str, MediaFile] | None = None,
    ) -> EnrichmentResult:
        concurrency = max(1, self._config.max_concurrent_analyses)
        semaphore_analysis = asyncio.Semaphore(concurrency)

        async def _process(reference: ContentReference) -> EnrichedItem:
            media_info: MediaFile | None = None
            if media_files and reference.media_key:
                media_info = media_files.get(reference.media_key)
                if media_info:
                    media_path = getattr(media_info, "dest_path", None)
                    if media_path:
                        reference.media_path = (
                            media_path if isinstance(media_path, Path) else Path(media_path)
                        )
                    reference.media_type = getattr(media_info, "media_type", None)

            if reference.media_path is not None and not reference.media_path.exists():
                reference.media_path = None

            if reference.url is None and reference.media_path is None:
                analysis = AnalysisResult(
                    summary=MEDIA_PLACEHOLDER_SUMMARY,
                    topics=[MEDIA_PLACEHOLDER_TOPIC],
                    actions=[],
                    relevance=max(1, self._config.relevance_threshold - 1),
                    raw_response=None,
                )
                return EnrichedItem(reference=reference, analysis=analysis)

            cache_key, cached_payload, cache_record = self._fetch_cache_entry(reference.url)
            if cache_key is not None and cached_payload is None:
                self._metrics["cache_misses"] = self._metrics.get("cache_misses", 0) + 1

            if cache_key is not None and cached_payload is not None:
                cached_item = self._analysis_from_cache(cached_payload)
                if cached_item:
                    self._metrics["cache_hits"] = self._metrics.get("cache_hits", 0) + 1
                    self._register_cache_hit(cache_key, cached_payload, cache_record)
                    return EnrichedItem(reference=reference, analysis=cached_item)

                self._metrics["cache_misses"] = self._metrics.get("cache_misses", 0) + 1
                cache = self._cache
                if cache is not None:
                    try:
                        cache.delete(cache_key)
                    except Exception:
                        pass

            async with semaphore_analysis:
                analysis = await self._analyze_reference(
                    reference,
                    client=client,
                    media_info=media_info,
                )
            if analysis.error:
                return EnrichedItem(
                    reference=reference,
                    analysis=None,
                    error=analysis.error,
                )

            cache = self._cache
            if cache is not None:
                self._store_in_cache(reference, analysis)
            return EnrichedItem(reference=reference, analysis=analysis)

        try:
            items = await asyncio.wait_for(
                asyncio.gather(*(_process(reference) for reference in references)),
                timeout=self._config.max_total_enrichment_time,
            )
        except TimeoutError:
            return EnrichmentResult(
                items=[],
                errors=[
                    "Tempo limite atingido ao enriquecer conteúdos (max_total_enrichment_time)."
                ],
            )

        result = EnrichmentResult(
            items=list(items),
        )
        for item in result.items:
            if item.error:
                url_display = item.reference.redacted_url() or "mídia"
                result.errors.append(f"Falha ao processar {url_display}: {item.error}")
        return result

    def _finalize_result(
        self,
        *,
        started_at: datetime,
        start: float,
        references: Sequence[ContentReference],
        result: EnrichmentResult,
    ) -> EnrichmentResult:
        duration = perf_counter() - start
        result.duration_seconds = duration

        finished_at = datetime.now(UTC)
        urls = tuple(sorted({r.url for r in references if r.url}))
        metrics = EnrichmentRunMetrics(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            total_references=len(references),
            analyzed_items=len(result.items),
            relevant_items=self._count_relevant_items(result.items),
            error_count=len(result.errors),
            domains=self._collect_domains(references),
            urls=urls,
            threshold=max(1, self._config.relevance_threshold),
        )
        result.metrics = metrics
        self._log_metrics(metrics, result.errors)
        self._write_metrics_csv(metrics, result.errors)
        return result

    def _count_relevant_items(self, items: Sequence[EnrichedItem]) -> int:
        threshold = max(1, self._config.relevance_threshold)
        return sum(1 for item in items if item.analysis and item.analysis.relevance >= threshold)

    @staticmethod
    def _collect_domains(references: Sequence[ContentReference]) -> tuple[str, ...]:
        domains = {_extract_domain(reference.url) for reference in references if reference.url}
        return tuple(sorted(filter(None, domains)))

    def _log_metrics(
        self,
        metrics: EnrichmentRunMetrics,
        errors: Sequence[str],
    ) -> None:
        urls_display = ", ".join(metrics.urls) if metrics.urls else "-"
        payload = metrics.to_dict()
        payload["errors"] = list(errors)
        logger.info(
            "Enrichment: %d/%d relevant items (≥%d) in %.2fs; urls=%s; errors=%d",
            metrics.relevant_items,
            metrics.analyzed_items,
            metrics.threshold,
            metrics.duration_seconds,
            urls_display,
            metrics.error_count,
            extra={"enrichment_metrics": payload},
        )

    def _write_metrics_csv(
        self,
        metrics: EnrichmentRunMetrics,
        errors: Sequence[str],
    ) -> None:
        path_value = self._config.metrics_csv_path
        if path_value is None:
            return

        path = Path(path_value)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return

        row = metrics.to_csv_row(errors)
        write_header = not path.exists()
        try:
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        except OSError:
            return

    def _prepare_enrichment_frame(
        self,
        df: pl.DataFrame,
        target_dates: Sequence[date] | None,
    ) -> pl.DataFrame | None:
        frame = ensure_message_schema(df)
        frame = self._filter_frame_by_dates(frame, target_dates)
        if frame is None:
            return None

        frame = self._prepare_base_frame(frame)
        frame = self._add_context_line(frame)
        frame = self._annotate_references(frame)
        return self._apply_context_window(frame)

    def _filter_frame_by_dates(
        self, frame: pl.DataFrame, target_dates: Sequence[date] | None
    ) -> pl.DataFrame | None:
        if target_dates:
            frame = frame.filter(pl.col("date").is_in(list(target_dates)))
        if frame.is_empty():
            return None
        return frame

    @staticmethod
    def _prepare_base_frame(frame: pl.DataFrame) -> pl.DataFrame:
        return (
            frame.sort(["date", "timestamp"])
            .with_columns(
                pl.col("message").fill_null("").alias("message"),
                pl.col("author").fill_null("").alias("author"),
            )
            .with_columns(pl.col("timestamp").dt.strftime("%H:%M").alias("__time_str"))
        )

    @staticmethod
    def _add_context_line(frame: pl.DataFrame) -> pl.DataFrame:
        fallback = pl.format(
            "{} — {}: {}",
            pl.col("__time_str").fill_null(""),
            pl.col("author"),
            pl.col("message"),
        )

        context_candidates: list[pl.Expr] = [fallback]

        if "original_line" in frame.columns:
            context_candidates.insert(
                0,
                pl.when(
                    pl.col("original_line").is_not_null()
                    & (pl.col("original_line").str.len_chars() > 0)
                )
                .then(pl.col("original_line"))
                .otherwise(None),
            )

        if "tagged_line" in frame.columns:
            context_candidates.insert(
                0,
                pl.when(
                    pl.col("tagged_line").is_not_null()
                    & (pl.col("tagged_line").str.len_chars() > 0)
                )
                .then(pl.col("tagged_line"))
                .otherwise(None),
            )

        return frame.with_columns(pl.coalesce(*context_candidates).alias("__context_line"))

    @staticmethod
    def _annotate_references(frame: pl.DataFrame) -> pl.DataFrame:
        attachment_key = pl.col("__context_line").map_elements(
            ContentEnricher._extract_attachment_key,
            return_dtype=pl.String,
        )
        media_token = pl.col("message").str.contains(MEDIA_TOKEN_RE.pattern)
        return frame.with_columns(
            pl.col("message").str.extract_all(URL_RE.pattern).alias("__urls"),
            attachment_key.alias("__attachment_key"),
            (media_token | attachment_key.is_not_null()).alias("__media_placeholder"),
        )

    @staticmethod
    def _extract_attachment_key(value: str | None) -> str | None:
        if not value:
            return None
        extracted = MediaExtractor._extract_attachment_segment(value)
        if extracted is None:
            return None
        sanitized, _, _ = extracted
        cleaned = sanitized.strip()
        return cleaned or None

    def _apply_context_window(self, frame: pl.DataFrame) -> pl.DataFrame:
        window = max(self._config.context_window, 0)
        if window <= 0:
            return frame.with_columns(
                pl.lit([], dtype=pl.List(pl.String)).alias("__context_before"),
                pl.lit([], dtype=pl.List(pl.String)).alias("__context_after"),
            )

        before_cols = [
            pl.col("__context_line").shift(i).over("date").alias(f"__before_{i}")
            for i in range(window, 0, -1)
        ]
        after_cols = [
            pl.col("__context_line").shift(-i).over("date").alias(f"__after_{i}")
            for i in range(1, window + 1)
        ]
        frame = frame.with_columns(before_cols + after_cols)
        frame = frame.with_columns(
            pl.concat_list([pl.col(f"__before_{i}") for i in range(window, 0, -1)])
            .list.drop_nulls()
            .alias("__context_before"),
            pl.concat_list([pl.col(f"__after_{i}") for i in range(1, window + 1)])
            .list.drop_nulls()
            .alias("__context_after"),
        )
        drop_cols = [
            *(f"__before_{i}" for i in range(window, 0, -1)),
            *(f"__after_{i}" for i in range(1, window + 1)),
        ]
        return frame.drop(drop_cols)

    def _extract_references_from_frame(self, frame: pl.DataFrame) -> list[ContentReference]:
        references: list[ContentReference] = []
        seen: set[tuple[str | None, str]] = set()

        url_rows = (
            frame.filter(pl.col("__urls").list.len() > 0)
            .explode("__urls")
            .filter(pl.col("__urls").str.len_chars() > 0)
        )

        for row in url_rows.iter_rows(named=True):
            url = row["__urls"]
            sender = row.get("author") or None
            key = (url, sender or "")
            if key in seen:
                continue
            seen.add(key)

            before_values = row.get("__context_before") or []
            after_values = row.get("__context_after") or []
            before = [item for item in before_values if item]
            after = [item for item in after_values if item]

            media_key = row.get("__attachment_key") or None
            media_key = media_key or None

            references.append(
                ContentReference(
                    date=row["date"],
                    url=url,
                    sender=sender,
                    timestamp=row.get("__time_str"),
                    message=row.get("message", ""),
                    context_before=before,
                    context_after=after,
                    media_key=media_key,
                )
            )

        placeholder_rows = frame.filter(
            pl.col("__media_placeholder") & (pl.col("__urls").list.len() == 0)
        )

        for row in placeholder_rows.iter_rows(named=True):
            context_line = row.get("__context_line", "") or ""
            attachment_key = row.get("__attachment_key") or None
            key = (attachment_key, context_line)
            if key in seen:
                continue
            seen.add(key)

            before_values = row.get("__context_before") or []
            after_values = row.get("__context_after") or []
            before = [item for item in before_values if item]
            after = [item for item in after_values if item]

            references.append(
                ContentReference(
                    date=row["date"],
                    url=None,
                    sender=row.get("author") or None,
                    timestamp=row.get("__time_str"),
                    message=row.get("message", ""),
                    context_before=before,
                    context_after=after,
                    is_media_placeholder=True,
                    media_key=attachment_key,
                )
            )

        return references


def extract_urls_from_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Extract URLs from DataFrame and return DataFrame with ``urls`` column."""

    if "message" not in df.columns:
        raise KeyError("DataFrame must have 'message' column")

    return df.with_columns(
        pl.col("message").fill_null("").str.extract_all(URL_RE.pattern).alias("urls")
    )


# TODO: This function seems to be a legacy or alternative implementation for
# extracting URL contexts. It uses `to_dicts()` which is not performant.
# It should be investigated if this function is still needed and, if so,
# if it can be refactored to use a more efficient Polars implementation.
def get_url_contexts_dataframe(df: pl.DataFrame, context_window: int = 3) -> pl.DataFrame:
    """Extract URLs with surrounding context from a conversation DataFrame."""

    if df.is_empty() or "urls" not in df.columns:
        return pl.DataFrame(
            {
                "url": [],
                "timestamp": [],
                "author": [],
                "message": [],
                "context_before": [],
                "context_after": [],
            },
            schema={
                "url": pl.String,
                "timestamp": pl.Datetime,
                "author": pl.String,
                "message": pl.String,
                "context_before": pl.String,
                "context_after": pl.String,
            },
        )

    df_sorted = df.sort("timestamp").with_row_index(name="row_index")
    rows = df_sorted.to_dicts()
    formatted_messages = [
        f"{row.get('time')} — {row.get('author')}: {row.get('message')}".strip() for row in rows
    ]

    results: list[dict[str, object]] = []
    row_count = len(rows)

    for row in rows:
        urls = row.get("urls") or []
        if not urls:
            continue

        idx = int(row.get("row_index", 0))
        start_before = max(0, idx - context_window)
        end_after = min(row_count, idx + context_window + 1)

        context_before = "\n".join(formatted_messages[start_before:idx])
        context_after = "\n".join(formatted_messages[idx + 1 : end_after])

        for url in urls:
            results.append(
                {
                    "url": url,
                    "timestamp": row.get("timestamp"),
                    "author": row.get("author"),
                    "message": row.get("message"),
                    "context_before": context_before,
                    "context_after": context_after,
                }
            )

    if not results:
        return pl.DataFrame(
            {
                "url": [],
                "timestamp": [],
                "author": [],
                "message": [],
                "context_before": [],
                "context_after": [],
            },
            schema={
                "url": pl.String,
                "timestamp": pl.Datetime,
                "author": pl.String,
                "message": pl.String,
                "context_before": pl.String,
                "context_after": pl.String,
            },
        )

    schema = {
        "url": pl.String,
        "timestamp": pl.Datetime,
        "author": pl.String,
        "message": pl.String,
        "context_before": pl.String,
        "context_after": pl.String,
    }

    return pl.DataFrame(results, schema=schema).select(
        [
            "url",
            "timestamp",
            "author",
            "message",
            "context_before",
            "context_after",
        ]
    )


__all__ = [
    "AnalysisResult",
    "ContentEnricher",
    "ContentReference",
    "EnrichedItem",
    "EnrichmentResult",
    "EnrichmentRunMetrics",
    "MESSAGE_RE",
    "extract_urls_from_dataframe",
    "get_url_contexts_dataframe",
]
