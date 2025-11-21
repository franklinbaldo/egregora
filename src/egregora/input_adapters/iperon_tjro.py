"""Adapter for TJRO Comunica API focused on IPERON-related proceedings."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import httpx
import ibis

from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
from egregora.input_adapters.base import AdapterMeta, InputAdapter

logger = logging.getLogger(__name__)


AUTHOR_NAMESPACE = UUID("1b7ca5a9-2fdb-4584-9621-a4a71af9d4a4")
RUN_IDENTIFIER = "adapter:iperon-tjro"
BASE_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"


@dataclass(slots=True)
class RequestPlan:
    """Configuration for querying the TJRO Comunica API."""

    urls: list[str] = field(default_factory=list)
    query_params: dict[str, Any] | None = None
    start_page: int = 1
    max_pages: int | None = None
    mock_items: list[dict[str, Any]] = field(default_factory=list)


class IperonTJROAdapter(InputAdapter):
    """Adapter that fetches diaries and notifications referencing IPERON from TJRO."""

    @property
    def source_name(self) -> str:  # noqa: D401
        return "TJRO Comunica API"

    @property
    def source_identifier(self) -> str:  # noqa: D401
        return "iperon-tjro"

    @property
    def content_summary(self) -> str:
        return (
            "Judicial communications published via the Brazilian TJRO Comunica API, "
            "filtered for proceedings involving IPERON."
        )

    @property
    def generation_instructions(self) -> str:
        return (
            "Treat each message as an official court notice. Highlight the case context, the tribunal action, "
            "and why it matters for IPERON rather than speculating beyond the published communication."
        )

    def get_adapter_metadata(self) -> AdapterMeta:
        """Metadata so registries can discover this adapter."""
        return {
            "name": "TJRO Comunica API",
            "version": "0.1.0",
            "source": self.source_identifier,
            "doc_url": "https://comunicaapi.pje.jus.br/api",
            "ir_version": "v1",
        }

    def parse(self, input_path: Path, *, timezone: str | None = None, **_: Any) -> ibis.Table:
        """Fetch communications and convert them to the IR schema."""
        plan = self._load_plan(input_path)
        items: list[dict[str, Any]] = []

        if plan.mock_items:
            items.extend(plan.mock_items)

        if plan.urls:
            for url in plan.urls:
                try:
                    items.extend(self._fetch_url(url))
                except Exception:
                    logger.exception("Failed to fetch data from %s", url)
        elif plan.query_params:
            items.extend(self._fetch_from_query(plan))

        if not items:
            logger.warning("No communications returned for %s", input_path)

        rows = [self._normalize_item(item, timezone) for item in items if isinstance(item, dict)]
        return ibis.memtable(rows, schema=IR_MESSAGE_SCHEMA)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def _load_plan(self, path: Path) -> RequestPlan:
        if not path.exists():
            msg = f"Config file not found: {path}"
            raise FileNotFoundError(msg)

        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            msg = f"Config file is empty: {path}"
            raise ValueError(msg)

        if path.suffix.lower() == ".json":
            data = json.loads(raw_text)
        else:
            urls = [line.strip() for line in raw_text.splitlines() if line.strip()]
            data = {"urls": urls}

        plan = RequestPlan()
        plan.urls = data.get("urls", [])
        plan.query_params = data.get("query") or data.get("filters")
        plan.start_page = int(data.get("start_page", 1))
        plan.max_pages = data.get("max_pages")
        if plan.max_pages is not None:
            plan.max_pages = int(plan.max_pages)
        plan.mock_items = data.get("mock_items", [])

        return plan

    # ------------------------------------------------------------------
    # API access
    # ------------------------------------------------------------------

    def _fetch_url(self, url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        return payload.get("items", [])

    def _fetch_from_query(self, plan: RequestPlan) -> list[dict[str, Any]]:
        params = dict(plan.query_params or {})
        params.setdefault("nomeParte", "IPERON")
        params.setdefault("siglaTribunal", "TJRO")
        params.setdefault("meio", "D")
        params.setdefault("itensPorPagina", 100)

        records: list[dict[str, Any]] = []
        page = max(plan.start_page, 1)
        while True:
            page_params = dict(params)
            page_params["pagina"] = page
            logger.info("Fetching TJRO page %s", page)
            batch = self._fetch_url(BASE_URL, params=page_params)
            if not batch:
                break
            records.extend(batch)
            page += 1
            if plan.max_pages and page > plan.max_pages:
                break
        return records

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_item(self, item: dict[str, Any], timezone: str | None) -> dict[str, Any]:
        ts = self._parse_timestamp(item, timezone)
        tribunal = item.get("siglaTribunal", "TJRO")
        author_raw = item.get("nomeOrgao") or f"{tribunal} - {item.get('tipoComunicacao', 'Comunicacao')}"
        author_uuid = str(uuid5(AUTHOR_NAMESPACE, author_raw.strip().lower()))
        processo = item.get("numero_processo") or item.get("numeroprocessocommascara")
        thread_id = str(processo or item.get("id"))
        msg_id = str(item.get("numeroComunicacao") or item.get("id"))

        attrs = {
            "tipoComunicacao": item.get("tipoComunicacao"),
            "nomeClasse": item.get("nomeClasse"),
            "codigoClasse": item.get("codigoClasse"),
            "meio": item.get("meiocompleto") or item.get("meio"),
            "destinatarios": item.get("destinatarios"),
            "destinatarioadvogados": item.get("destinatarioadvogados"),
            "link": item.get("link"),
        }

        text = self._build_body(item, processo)

        return {
            "event_id": str(item.get("id")),
            "tenant_id": tribunal,
            "source": self.source_identifier,
            "thread_id": thread_id,
            "msg_id": msg_id,
            "ts": ts,
            "author_raw": author_raw,
            "author_uuid": author_uuid,
            "text": text,
            "media_url": item.get("link"),
            "media_type": "url" if item.get("link") else None,
            "attrs": json.dumps(attrs),
            "pii_flags": None,
            "created_at": ts,
            "created_by_run": RUN_IDENTIFIER,
        }

    def _build_body(self, item: dict[str, Any], processo: Any) -> str:
        parts: list[str] = []
        texto = item.get("texto")
        if texto:
            parts.append(texto.strip())

        details: list[str] = []
        if processo:
            details.append(f"Processo: {processo}")
        if item.get("tipoComunicacao"):
            details.append(f"Tipo: {item['tipoComunicacao']}")
        if item.get("nomeClasse"):
            details.append(f"Classe: {item['nomeClasse']}")
        if item.get("link"):
            details.append(f"Link: {item['link']}")
        if details:
            parts.append("\n".join(details))

        return "\n\n".join(parts).strip() or "Comunicação publicada sem texto."

    def _parse_timestamp(self, item: dict[str, Any], tz_name: str | None) -> datetime:
        candidates = [
            item.get("data_disponibilizacao"),
            item.get("dataDisponibilizacao"),
            item.get("datadisponibilizacao"),
        ]
        for value in candidates:
            if not value:
                continue
            if isinstance(value, datetime):
                ts = value
            else:
                ts = self._parse_date_string(str(value))
            if ts:
                break
        else:
            ts = datetime.now(tz=UTC)

        if tz_name:
            try:
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(tz_name)
                ts = ts.astimezone(tz).astimezone(UTC)
            except Exception:
                logger.warning("Invalid timezone %s, defaulting to UTC", tz_name)
                ts = ts.astimezone(UTC)
        else:
            ts = ts.astimezone(UTC)
        return ts

    def _parse_date_string(self, raw: str) -> datetime:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        return datetime.now(tz=UTC)
