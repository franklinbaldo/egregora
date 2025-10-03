"""Expose the local newsletter RAG index through the Model Context Protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ..rag.core import NewsletterRAG, SearchHit
from ..rag.query_gen import QueryGenerator
from .config import MCPServerConfig
from .tools import format_newsletter_listing, format_search_hits

try:  # pragma: no cover - optional dependency
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        EmbeddedResource,
        Resource,
        ResourceTemplate,
        TextContent,
        Tool,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - gracefully handle missing dependency
    Server = None  # type: ignore
    NotificationOptions = None  # type: ignore
    InitializationOptions = None  # type: ignore

    @dataclass  # type: ignore[name-defined]
    class TextContent:  # type: ignore[misc]
        type: str
        text: str

    @dataclass  # type: ignore[name-defined]
    class Tool:  # type: ignore[misc]
        name: str
        description: str
        inputSchema: dict

    EmbeddedResource = Resource = ResourceTemplate = object  # type: ignore
    MCP_IMPORT_ERROR = exc
else:  # pragma: no cover - exercised when dependency available
    MCP_IMPORT_ERROR = None


def _identity_decorator(func):
    return func


if MCP_IMPORT_ERROR is None:
    app = Server("egregora-rag")
    list_tools = app.list_tools
    call_tool = app.call_tool
    read_resource = app.read_resource
else:  # pragma: no cover - fallback when dependency missing
    class _PlaceholderServer:
        def list_tools(self):
            return _identity_decorator

        def call_tool(self):
            return _identity_decorator

        def read_resource(self):
            return _identity_decorator

        def run_stdio(self):  # pragma: no cover - runtime error to inform user
            raise RuntimeError(
                "O pacote 'mcp' não está instalado. Execute 'pip install mcp' "
                "para habilitar o servidor."
            )

    app = _PlaceholderServer()
    list_tools = app.list_tools
    call_tool = app.call_tool
    read_resource = app.read_resource


class RAGServer:
    """Wrapper que expõe o RAG através do MCP."""

    def __init__(self, config_path: Path | None = None) -> None:
        config = MCPServerConfig.from_path(config_path)
        self.config = config
        self.rag = NewsletterRAG(
            newsletters_dir=config.newsletters_dir,
            cache_dir=config.cache_dir,
            config=config.rag,
        )
        self.query_gen = QueryGenerator(config.rag)
        self._indexed = False

    async def ensure_indexed(self) -> None:
        if not self._indexed:
            await asyncio.to_thread(self.rag.load_index)
            self._indexed = True

    async def search_newsletters(
        self,
        *,
        query: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
        exclude_recent_days: int | None = None,
    ) -> list[SearchHit]:
        await self.ensure_indexed()
        return await asyncio.to_thread(
            self.rag.search,
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
            exclude_recent_days=exclude_recent_days,
        )

    async def generate_query(self, *, transcripts: str, model: str | None = None) -> dict[str, Any]:
        result = await asyncio.to_thread(self.query_gen.generate, transcripts, model=model)
        return {
            "search_query": result.search_query,
            "keywords": result.keywords,
            "main_topics": result.main_topics,
            "context": result.context,
        }

    async def get_newsletter(self, *, date_str: str) -> str | None:
        await self.ensure_indexed()
        newsletter_path = self.config.newsletters_dir / f"{date_str}.md"
        if newsletter_path.exists():
            return newsletter_path.read_text(encoding="utf-8")
        return None

    async def list_newsletters(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        directory = self.config.newsletters_dir
        if not directory.exists():
            return []

        files = sorted(directory.glob("*.md"), key=lambda path: path.stem, reverse=True)
        selected = files[offset : offset + limit]
        return [
            {
                "date": path.stem,
                "path": str(path),
                "size_kb": max(1, path.stat().st_size // 1024),
            }
            for path in selected
        ]

    async def get_stats(self) -> dict[str, Any]:
        await self.ensure_indexed()
        stats = await asyncio.to_thread(self.rag.get_stats)
        return {
            "total_newsletters": stats.total_newsletters,
            "total_chunks": stats.total_chunks,
            "last_updated": stats.last_updated.isoformat() if stats.last_updated else None,
            "index_path": str(stats.index_path),
        }

    async def reindex(self, *, force: bool = False) -> dict[str, int]:
        result = await asyncio.to_thread(self.rag.update_index, force_reindex=force)
        return {
            "new": result.new_count,
            "modified": result.modified_count,
            "deleted": result.deleted_count,
            "total_chunks": result.total_chunks,
        }


rag_server: RAGServer | None = None


@list_tools()
async def handle_list_tools() -> List[Tool]:  # type: ignore[valid-type]
    if MCP_IMPORT_ERROR is not None:
        raise RuntimeError(
            "O pacote 'mcp' não está instalado; instale-o para listar as tools."
        )

    return [
        Tool(
            name="search_newsletters",
            description=(
                "Busca trechos relevantes em newsletters anteriores usando "
                "busca semântica. Retorna chunks similares à query fornecida."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query de busca (pergunta, tópicos, keywords)",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Número máximo de resultados (padrão: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "min_similarity": {
                        "type": "number",
                        "description": "Similaridade mínima 0-1 (padrão: 0.7)",
                        "default": 0.7,
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "exclude_recent_days": {
                        "type": "integer",
                        "description": "Excluir newsletters dos últimos N dias (padrão: 7)",
                        "default": 7,
                        "minimum": 0,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="generate_search_query",
            description=(
                "Gera uma query de busca otimizada a partir de transcritos "
                "de conversas. Usa heurísticas para extrair tópicos principais."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transcripts": {
                        "type": "string",
                        "description": "Texto dos transcritos a analisar",
                    },
                    "model": {
                        "type": "string",
                        "description": "Modelo LLM a usar (compatível com futuras integrações)",
                        "default": "gemini-2.0-flash-exp",
                    },
                },
                "required": ["transcripts"],
            },
        ),
        Tool(
            name="get_newsletter",
            description="Retorna o conteúdo completo de uma newsletter específica por data (YYYY-MM-DD).",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Data da newsletter (YYYY-MM-DD)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    }
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="list_newsletters",
            description="Lista newsletters disponíveis com paginação.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de resultados (padrão: 50)",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset para paginação (padrão: 0)",
                        "default": 0,
                        "minimum": 0,
                    },
                },
            },
        ),
        Tool(
            name="get_rag_stats",
            description="Retorna estatísticas do sistema RAG (chunks, cache, etc).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="reindex_newsletters",
            description=(
                "Atualiza o índice do RAG processando newsletters novas ou modificadas. "
                "Use force=true para reindexar tudo."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Se true, reprocessa todas as newsletters",
                        "default": False,
                    }
                },
            },
        ),
    ]


@call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:  # type: ignore[valid-type]
    if MCP_IMPORT_ERROR is not None:
        raise RuntimeError(
            "O pacote 'mcp' não está instalado; instale-o para usar as ferramentas."
        )

    if rag_server is None:
        return [TextContent(type="text", text="Erro: RAG server não inicializado")]

    try:
        if name == "search_newsletters":
            hits = await rag_server.search_newsletters(**arguments)
            markdown = format_search_hits(hits)
            return [TextContent(type="text", text=markdown)]

        if name == "generate_search_query":
            data = await rag_server.generate_query(**arguments)
            markdown = "\n".join(
                [
                    "# Query Gerada\n",
                    f"**Tópicos Principais:** {', '.join(data['main_topics'])}",
                    f"**Keywords:** {', '.join(data['keywords'])}",
                    "",
                    f"**Query de Busca:**\n{data['search_query']}",
                    "",
                    f"**Contexto:**\n{data['context']}",
                ]
            )
            return [TextContent(type="text", text=markdown.strip())]

        if name == "get_newsletter":
            content = await rag_server.get_newsletter(date_str=arguments["date"])
            if content:
                return [TextContent(type="text", text=content)]
            return [TextContent(type="text", text="Newsletter não encontrada.")]

        if name == "list_newsletters":
            entries = await rag_server.list_newsletters(**arguments)
            markdown = format_newsletter_listing(entries)
            return [TextContent(type="text", text=markdown)]

        if name == "get_rag_stats":
            stats = await rag_server.get_stats()
            lines = ["# Estatísticas do RAG\n"]
            for key, value in stats.items():
                lines.append(f"- **{key}**: {value}")
            return [TextContent(type="text", text="\n".join(lines))]

        if name == "reindex_newsletters":
            stats = await rag_server.reindex(**arguments)
            lines = ["# Resultado da Reindexação\n"]
            for key, value in stats.items():
                lines.append(f"- **{key}**: {value}")
            return [TextContent(type="text", text="\n".join(lines))]

        return [TextContent(type="text", text=f"Tool desconhecida: {name}")]
    except Exception as exc:  # pragma: no cover - defensive logging
        return [TextContent(type="text", text=f"Erro ao executar tool: {exc}")]


@read_resource()
async def handle_read_resource(uri: str) -> str:
    if rag_server is None:
        raise RuntimeError("RAG server não inicializado")

    if not uri.startswith("newsletter://"):
        raise ValueError(f"URI inválida: {uri}")

    date_str = uri.replace("newsletter://", "")
    content = await rag_server.get_newsletter(date_str=date_str)
    if content is None:
        raise ValueError(f"Newsletter não encontrada: {date_str}")
    return content


async def main(config_path: Path | None = None) -> None:
    if MCP_IMPORT_ERROR is not None:
        raise RuntimeError(
            "O pacote 'mcp' não está instalado. Instale 'mcp' para executar o servidor."
        ) from MCP_IMPORT_ERROR

    global rag_server
    rag_server = RAGServer(config_path=config_path)

    print("[MCP Server] Inicializando RAG...")
    await rag_server.ensure_indexed()
    print("[MCP Server] ✅ RAG inicializado")
    print("[MCP Server] Servidor pronto!")

    async with app.run_stdio():  # type: ignore[union-attr]
        await asyncio.Event().wait()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
