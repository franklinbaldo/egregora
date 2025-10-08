"""Content enrichment orchestrator using Gemini's native URL support."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Sequence, TYPE_CHECKING

try:  # pragma: no cover - optional dependency
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - allows the module to load without dependency
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from urllib.parse import urlparse

import polars as pl
from pydantic import ValidationError
from pydantic_ai import Agent

from .cache_manager import CacheManager
from .config import EnrichmentConfig
from .gemini_manager import GeminiQuotaError
from .llm_models import ActionItem, SummaryResponse
from .schema import ensure_message_schema

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .gemini_manager import GeminiManager

MESSAGE_RE = re.compile(
    r"^(?P<time>\d{1,2}:\d{2})\s+[—\-–]\s+(?P<sender>[^:]+):\s*(?P<message>.*)$"
)
URL_RE = re.compile(r"(https?://[^\s>\)]+)", re.IGNORECASE)
MEDIA_TOKEN_RE = re.compile(r"<m[íi]dia oculta>", re.IGNORECASE)

CACHE_RECORD_VERSION = "2.0"

SUMMARY_AGENT = Agent(output_type=SummaryResponse)

MEDIA_PLACEHOLDER_SUMMARY = (
    "Mídia sem descrição compartilhada; peça detalhes se necessário."
)


COLUMN_SEPARATOR = "; "


logger = logging.getLogger(__name__)


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

    def context_block(self) -> str:
        """Return a human-friendly snippet of the surrounding chat messages."""

        before = " | ".join(self.context_before)
        after = " | ".join(self.context_after)
        return " || ".join(filter(None, [before, self.message, after]))


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
    metrics: "EnrichmentRunMetrics | None" = None

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
            lines.append(f"{index}. URL: {ref.url or 'Mídia sem link'}")
            if ref.sender or ref.timestamp:
                sender = ref.sender or "(autor desconhecido)"
                when = ref.timestamp or "horário desconhecido"
                lines.append(
                    f"   Remetente: {sender.strip()} às {when} em {ref.date.isoformat()}"
                )
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
            "threshold": self.threshold,
        }

    def to_csv_row(self, errors: Sequence[str]) -> dict[str, object]:
        base = self.to_dict()
        base["domains"] = COLUMN_SEPARATOR.join(self.domains)
        base["errors"] = COLUMN_SEPARATOR.join(errors)
        return base


class ContentEnricher:
    """High-level orchestrator that extracts and analyzes shared links."""

    def __init__(
        self,
        config: EnrichmentConfig,
        *,
        cache_manager: CacheManager | None = None,
        gemini_manager: "GeminiManager | None" = None,
    ) -> None:
        self._config = config
        self._cache = cache_manager
        self._gemini_manager = gemini_manager
        self._metrics: dict[str, int] = {
            "llm_calls": 0,
            "estimated_tokens": 0,
            "cache_hits": 0,
        }

    @property
    def metrics(self) -> dict[str, int]:
        """Return LLM usage metrics for observability."""

        return dict(self._metrics)

    async def enrich(
        self,
        transcripts: Sequence[tuple[date, str]],
        *,
        client: genai.Client | None,
    ) -> EnrichmentResult:
        """Run the enrichment pipeline leveraging Gemini's URL ingestion."""

        start = perf_counter()
        started_at = datetime.now(timezone.utc)
        references: list[ContentReference] = []
        if not self._config.enabled:
            result = EnrichmentResult()
            return self._finalize_result(
                started_at=started_at,
                start=start,
                references=references,
                result=result,
            )

        references = self._extract_references(transcripts)
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
        )
        return self._finalize_result(
            started_at=started_at,
            start=start,
            references=references,
            result=result,
        )

    async def enrich_dataframe(
        self,
        df: pl.DataFrame,
        *,
        client: genai.Client | None,
        target_dates: Sequence[date] | None = None,
    ) -> EnrichmentResult:
        """DataFrame-native enrichment pipeline using Polars expressions."""

        start = perf_counter()
        started_at = datetime.now(timezone.utc)
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
        )
        return self._finalize_result(
            started_at=started_at,
            start=start,
            references=references,
            result=result,
        )

    async def _analyze_reference(
        self,
        reference: ContentReference,
        client: genai.Client | None,
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

        parts = [types.Part.from_text(text=prompt)]
        if reference.url:
            try:
                parts.append(types.Part.from_uri(file_uri=reference.url))
            except Exception:  # pragma: no cover - depends on mimetype detection
                fallback = f"URL compartilhada: {reference.url}"
                parts.append(types.Part.from_text(text=fallback))
        contents = [types.Content(role="user", parts=parts)]
        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )

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

    def _store_in_cache(
        self, reference: ContentReference, analysis: AnalysisResult
    ) -> None:
        if not self._cache or not reference.url:
            return

        enrichment_payload = {
            "summary": analysis.summary,
            "topics": list(analysis.topics),
            "actions": [item.model_dump() for item in analysis.actions],
            "relevance": analysis.relevance,
            "raw_response": analysis.raw_response,
        }
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        domain = urlparse(reference.url).netloc if reference.url else None
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
        payload = {
            "model": self._config.enrichment_model,
            "analyzed_at": timestamp,
            "enrichment": enrichment_payload,
            "context": context,
            "metadata": {k: v for k, v in metadata.items() if v is not None},
            "version": CACHE_RECORD_VERSION,
        }
        try:
            self._cache.set(reference.url, payload)
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
        estimated = max(1, (len(prompt) + len(response_text or "")) // 4)
        self._metrics["estimated_tokens"] = self._metrics.get("estimated_tokens", 0) + estimated

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

    def _extract_references(
        self, transcripts: Sequence[tuple[date, str]]
    ) -> list[ContentReference]:
        references: list[ContentReference] = []
        seen: set[tuple[str | None, str]] = set()
        window = max(self._config.context_window, 0)

        for transcript_date, transcript in transcripts:
            lines = transcript.splitlines()
            for index, raw_line in enumerate(lines):
                line = raw_line.strip()
                if not line:
                    continue

                media_match = MEDIA_TOKEN_RE.search(line)
                urls = URL_RE.findall(line)
                message = line
                sender = None
                timestamp = None
                match = MESSAGE_RE.match(line)
                if match:
                    timestamp = match.group("time")
                    sender = match.group("sender").strip()
                    message = match.group("message").strip()

                context_before = [
                    lines[pos].strip()
                    for pos in range(max(0, index - window), index)
                    if lines[pos].strip()
                ]
                context_after = [
                    lines[pos].strip()
                    for pos in range(index + 1, min(len(lines), index + window + 1))
                    if lines[pos].strip()
                ]

                if media_match and not urls:
                    key = (None, line)
                    if key in seen:
                        continue
                    seen.add(key)
                    references.append(
                        ContentReference(
                            date=transcript_date,
                            url=None,
                            sender=sender,
                            timestamp=timestamp,
                            message=message,
                            context_before=context_before,
                            context_after=context_after,
                            is_media_placeholder=True,
                        )
                    )
                    continue

                for url in urls:
                    key = (url, sender or "")
                    if key in seen:
                        continue
                    seen.add(key)
                    references.append(
                        ContentReference(
                            date=transcript_date,
                            url=url,
                            sender=sender,
                            timestamp=timestamp,
                            message=message,
                            context_before=context_before,
                            context_after=context_after,
                        )
                    )

        return references

    async def enrich_from_dataframe(
        self,
        df: pl.DataFrame,
        *,
        client: genai.Client | None,
        target_dates: list[date] | None = None,
    ) -> EnrichmentResult:
        """Backward compatible wrapper around :meth:`enrich_dataframe`."""

        return await self.enrich_dataframe(
            df,
            client=client,
            target_dates=target_dates,
        )

    async def _enrich_references(
        self,
        references: Sequence[ContentReference],
        *,
        client: genai.Client | None,
    ) -> EnrichmentResult:
        concurrency = max(1, self._config.max_concurrent_analyses)
        semaphore_analysis = asyncio.Semaphore(concurrency)

        async def _process(reference: ContentReference) -> EnrichedItem:
            if reference.is_media_placeholder or not reference.url:
                analysis = AnalysisResult(
                    summary=MEDIA_PLACEHOLDER_SUMMARY,
                    topics=["Conteúdo multimídia sem transcrição"],
                    actions=[],
                    relevance=max(1, self._config.relevance_threshold - 1),
                    raw_response=None,
                )
                return EnrichedItem(reference=reference, analysis=analysis)

            cached_item: AnalysisResult | None = None
            if self._cache:
                cached_payload = self._cache.get(reference.url)
                if cached_payload:
                    cached_item = self._analysis_from_cache(cached_payload)
            if cached_item:
                self._metrics["cache_hits"] = self._metrics.get("cache_hits", 0) + 1
                return EnrichedItem(reference=reference, analysis=cached_item)

            async with semaphore_analysis:
                analysis = await self._analyze_reference(
                    reference,
                    client=client,
                )
            if analysis.error:
                return EnrichedItem(
                    reference=reference,
                    analysis=None,
                    error=analysis.error,
                )

            if self._cache:
                self._store_in_cache(reference, analysis)
            return EnrichedItem(reference=reference, analysis=analysis)

        try:
            items = await asyncio.wait_for(
                asyncio.gather(*(_process(reference) for reference in references)),
                timeout=self._config.max_total_enrichment_time,
            )
        except asyncio.TimeoutError:
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
                result.errors.append(
                    f"Falha ao processar {item.reference.url or 'mídia'}: {item.error}"
                )
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

        finished_at = datetime.now(timezone.utc)
        metrics = EnrichmentRunMetrics(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            total_references=len(references),
            analyzed_items=len(result.items),
            relevant_items=self._count_relevant_items(result.items),
            error_count=len(result.errors),
            domains=self._collect_domains(references),
            threshold=max(1, self._config.relevance_threshold),
        )
        result.metrics = metrics
        self._log_metrics(metrics, result.errors)
        self._write_metrics_csv(metrics, result.errors)
        return result

    def _count_relevant_items(self, items: Sequence[EnrichedItem]) -> int:
        threshold = max(1, self._config.relevance_threshold)
        return sum(
            1
            for item in items
            if item.analysis and item.analysis.relevance >= threshold
        )

    @staticmethod
    def _collect_domains(references: Sequence[ContentReference]) -> tuple[str, ...]:
        domains = {
            urlparse(reference.url).netloc
            for reference in references
            if reference.url
        }
        return tuple(sorted(filter(None, domains)))

    def _log_metrics(
        self,
        metrics: "EnrichmentRunMetrics",
        errors: Sequence[str],
    ) -> None:
        domains_display = ", ".join(metrics.domains) if metrics.domains else "-"
        payload = metrics.to_dict()
        payload["errors"] = list(errors)
        logger.info(
            "Enrichment: %d/%d relevant items (≥%d) in %.2fs; domains=%s; errors=%d",
            metrics.relevant_items,
            metrics.analyzed_items,
            metrics.threshold,
            metrics.duration_seconds,
            domains_display,
            metrics.error_count,
            extra={"enrichment_metrics": payload},
        )

    def _write_metrics_csv(
        self,
        metrics: "EnrichmentRunMetrics",
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
        if target_dates:
            frame = frame.filter(pl.col("date").is_in(list(target_dates)))

        if frame.is_empty():
            return None

        frame = frame.sort(["date", "timestamp"])

        frame = frame.with_columns(
            pl.col("message").fill_null("").alias("message"),
            pl.col("author").fill_null("").alias("author"),
        )

        frame = frame.with_columns(
            pl.col("timestamp").dt.strftime("%H:%M").alias("__time_str")
        )

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

        frame = frame.with_columns(
            pl.coalesce(*context_candidates).alias("__context_line")
        )

        frame = frame.with_columns(
            pl.col("message")
            .str.extract_all(URL_RE.pattern)
            .alias("__urls"),
            pl.col("message")
            .str.contains(MEDIA_TOKEN_RE.pattern)
            .alias("__media_placeholder"),
        )

        window = max(self._config.context_window, 0)
        if window > 0:
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
                pl.concat_list(
                    [pl.col(f"__before_{i}") for i in range(window, 0, -1)]
                )
                .list.drop_nulls()
                .alias("__context_before"),
                pl.concat_list(
                    [pl.col(f"__after_{i}") for i in range(1, window + 1)]
                )
                .list.drop_nulls()
                .alias("__context_after"),
            )
            drop_cols = [
                *(f"__before_{i}" for i in range(window, 0, -1)),
                *(f"__after_{i}" for i in range(1, window + 1)),
            ]
            frame = frame.drop(drop_cols)
        else:
            frame = frame.with_columns(
                pl.lit([], dtype=pl.List(pl.String)).alias("__context_before"),
                pl.lit([], dtype=pl.List(pl.String)).alias("__context_after"),
            )

        return frame

    def _extract_references_from_frame(
        self, frame: pl.DataFrame
    ) -> list[ContentReference]:
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

            references.append(
                ContentReference(
                    date=row["date"],
                    url=url,
                    sender=sender,
                    timestamp=row.get("__time_str"),
                    message=row.get("message", ""),
                    context_before=before,
                    context_after=after,
                )
            )

        placeholder_rows = frame.filter(
            pl.col("__media_placeholder") & (pl.col("__urls").list.len() == 0)
        )

        for row in placeholder_rows.iter_rows(named=True):
            context_line = row.get("__context_line", "") or ""
            key = (None, context_line)
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
                )
            )

        return references

    def _dataframe_to_transcripts(
        self,
        df: pl.DataFrame,
        target_dates: list[date] | None = None,
    ) -> list[tuple[date, str]]:
        """Convert DataFrame to transcript format for compatibility."""

        if target_dates:
            df = df.filter(pl.col("date").is_in(target_dates))

        if df.is_empty():
            return []

        df_sorted = df.sort("timestamp")
        transcripts: list[tuple[date, str]] = []

        for day_df in df_sorted.partition_by("date", maintain_order=True):
            date_value = day_df.get_column("date")[0]
            if "original_line" in day_df.columns:
                lines = [line or "" for line in day_df.get_column("original_line").to_list()]
            else:
                times = day_df.get_column("time").to_list()
                authors = day_df.get_column("author").to_list()
                messages = day_df.get_column("message").to_list()
                lines = [
                    f"{time} — {author}: {message}"
                    for time, author, message in zip(times, authors, messages)
                ]
            transcripts.append((date_value, "\n".join(lines)))

        return transcripts


def extract_urls_from_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Extract URLs from DataFrame and return DataFrame with ``urls`` column."""

    if "message" not in df.columns:
        raise KeyError("DataFrame must have 'message' column")

    return df.with_columns(
        pl.col("message")
        .fill_null("")
        .str.extract_all(URL_RE.pattern)
        .alias("urls")
    )


def get_url_contexts_dataframe(
    df: pl.DataFrame, context_window: int = 3
) -> pl.DataFrame:
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
        f"{row.get('time')} — {row.get('author')}: {row.get('message')}".strip()
        for row in rows
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
    "extract_urls_from_dataframe",
    "get_url_contexts_dataframe",
]
