"""Content enrichment orchestrator using Gemini's native URL support."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
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

from .cache_manager import CacheManager
from .config import EnrichmentConfig
from .gemini_manager import GeminiQuotaError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .gemini_manager import GeminiManager

MESSAGE_RE = re.compile(
    r"^(?P<time>\d{1,2}:\d{2})\s+[—\-–]\s+(?P<sender>[^:]+):\s*(?P<message>.*)$"
)
URL_RE = re.compile(r"(https?://[^\s>\)]+)", re.IGNORECASE)
MEDIA_TOKEN_RE = re.compile(r"<m[íi]dia oculta>", re.IGNORECASE)

CACHE_RECORD_VERSION = "1.0"

MEDIA_PLACEHOLDER_SUMMARY = (
    "Mídia sem descrição compartilhada; peça detalhes se necessário."
)


@dataclass(slots=True)
class AnalysisResult:
    """Structured information returned by Gemini."""

    summary: str | None
    key_points: list[str]
    tone: str | None
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
            if analysis and analysis.key_points:
                lines.append("   Pontos-chave:")
                for point in analysis.key_points:
                    lines.append(f"     - {point}")
            if analysis and analysis.tone:
                lines.append(f"   Tom: {analysis.tone}")
            if analysis:
                lines.append(f"   Relevância estimada: {analysis.relevance}/5")
            if ref.context_before or ref.context_after:
                lines.append(f"   Contexto: {ref.context_block()}")
        lines.append("<<<ENRIQUECIMENTO_FIM>>>")
        return "\n".join(lines)


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

    async def enrich(
        self,
        transcripts: Sequence[tuple[date, str]],
        *,
        client: genai.Client | None,
    ) -> EnrichmentResult:
        """Run the enrichment pipeline leveraging Gemini's URL ingestion."""

        start = perf_counter()
        if not self._config.enabled:
            return EnrichmentResult(duration_seconds=perf_counter() - start)

        references = self._extract_references(transcripts)
        references = references[: self._config.max_links]

        if not references:
            return EnrichmentResult(duration_seconds=perf_counter() - start)

        concurrency = max(1, self._config.max_concurrent_analyses)
        semaphore_analysis = asyncio.Semaphore(concurrency)

        async def _process(reference: ContentReference) -> EnrichedItem:
            if reference.is_media_placeholder or not reference.url:
                analysis = AnalysisResult(
                    summary=MEDIA_PLACEHOLDER_SUMMARY,
                    key_points=["Mensagem sugere conteúdo multimídia sem transcrição."],
                    tone="indeterminado",
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
            duration = perf_counter() - start
            return EnrichmentResult(
                items=[],
                errors=[
                    "Tempo limite atingido ao enriquecer conteúdos (max_total_enrichment_time)."
                ],
                duration_seconds=duration,
            )

        duration = perf_counter() - start
        result = EnrichmentResult(
            items=list(items),
            duration_seconds=duration,
        )
        for item in result.items:
            if item.error:
                result.errors.append(
                    f"Falha ao processar {item.reference.url or 'mídia'}: {item.error}"
                )
        return result

    async def _analyze_reference(
        self,
        reference: ContentReference,
        client: genai.Client | None,
    ) -> AnalysisResult:
        manager = self._gemini_manager

        if manager is None and (types is None or client is None):
            return AnalysisResult(
                summary=None,
                key_points=[],
                tone=None,
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
                key_points=[],
                tone=None,
                relevance=1,
                raw_response=None,
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover - depends on network/model
            return AnalysisResult(
                summary=None,
                key_points=[],
                tone=None,
                relevance=1,
                raw_response=None,
                error=str(exc),
            )

        return self._parse_response(response)

    def _store_in_cache(
        self, reference: ContentReference, analysis: AnalysisResult
    ) -> None:
        if not self._cache or not reference.url:
            return

        enrichment_payload = asdict(analysis)
        enrichment_payload.pop("error", None)
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
        key_points = [
            point.strip()
            for point in enrichment.get("key_points", [])
            if isinstance(point, str)
        ]
        tone = self._coerce_string(enrichment.get("tone"))
        relevance = enrichment.get("relevance")
        if not isinstance(relevance, int):
            relevance = 1

        raw_response = enrichment.get("raw_response")
        if raw_response is not None and not isinstance(raw_response, str):
            raw_response = str(raw_response)

        return AnalysisResult(
            summary=summary,
            key_points=key_points,
            tone=tone,
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
                key_points=[],
                tone=None,
                relevance=1,
                raw_response=None,
                error="Resposta vazia do modelo.",
            )

        raw_text = raw_text.strip()
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = {
                "summary": raw_text,
                "key_points": [],
                "tone": None,
                "relevance": 1,
            }

        summary = ContentEnricher._coerce_string(payload.get("summary"))
        key_points = [
            point.strip()
            for point in payload.get("key_points", [])
            if isinstance(point, str)
        ]
        tone = ContentEnricher._coerce_string(payload.get("tone"))
        relevance = payload.get("relevance")
        if not isinstance(relevance, int):
            relevance = 1

        return AnalysisResult(
            summary=summary,
            key_points=key_points,
            tone=tone,
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
            "com as chaves: summary (string), key_points (lista com até 3 itens), "
            "tone (string curta) e relevance (inteiro de 1 a 5 indicando utilidade "
            "para o grupo). Se não houver dados suficientes, defina relevance = 1 e "
            "explique o motivo no summary. Dados do chat:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _coerce_string(value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

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
        """Enhanced DataFrame-native enrichment pipeline."""

        transcripts = self._dataframe_to_transcripts(df, target_dates)
        return await self.enrich(transcripts, client=client)

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
    "extract_urls_from_dataframe",
    "get_url_contexts_dataframe",
]
