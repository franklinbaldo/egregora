"""Expose the local post RAG index through the Model Context Protocol."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from llama_index.core.schema import NodeWithScore

from ..rag.index import PostRAG
from ..rag.keyword_utils import KeywordProvider, build_llm_keyword_provider
from ..rag.query_gen import QueryGenerator
from .config import MCPServerConfig
from .tools import format_post_listing, format_search_hits

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


DEFAULT_KEYWORD_MODEL = "gemini-2.0-flash-exp"


class RAGServer:
    """Wrapper que expõe o RAG através do MCP."""

    def __init__(self, config_path: Path | None = None) -> None:
        config = MCPServerConfig.from_path(config_path)
        self.config = config
        self.rag = PostRAG(
            posts_dir=config.posts_dir,
            cache_dir=config.cache_dir,
            config=config.rag,
        )
        self.query_gen = QueryGenerator(config.rag)
        self._gemini_client: Any | None = None
        self._keyword_providers: dict[str, KeywordProvider] = {}
        self._indexed = False

    def _ensure_gemini_client(self) -> Any:
        if self._gemini_client is not None:
            return self._gemini_client

        try:  # pragma: no cover - optional dependency
            from google import genai  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "A dependência opcional 'google-genai' não está instalada. "
                "Instale-a para habilitar a extração de palavras-chave."
            ) from exc

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Defina GEMINI_API_KEY ou GOOGLE_API_KEY no ambiente para gerar keywords."
            )

        self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    def _get_keyword_provider(self, model: str | None) -> KeywordProvider:
        model_name = (model or DEFAULT_KEYWORD_MODEL).strip()
        if not model_name:
            model_name = DEFAULT_KEYWORD_MODEL

        cached = self._keyword_providers.get(model_name)
        if cached is not None:
            return cached

        client = self._ensure_gemini_client()
        provider = build_llm_keyword_provider(client, model=model_name)
        self._keyword_providers[model_name] = provider
        return provider

    async def ensure_indexed(self) -> None:
        if not self._indexed:
            await asyncio.to_thread(self.rag.load_index)
            self._indexed = True

    async def search_posts(
        self,
        *,
        query: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
        exclude_recent_days: int | None = None,
    ) -> list[NodeWithScore]:
        await self.ensure_indexed()
        return await asyncio.to_thread(
            self.rag.search,
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
            exclude_recent_days=exclude_recent_days,
        )

    async def generate_query(
        self, *, transcripts: str, model: str | None = None
    ) -> dict[str, Any]:
        provider = self._get_keyword_provider(model)
        result = await asyncio.to_thread(
            self.query_gen.generate,
            transcripts,
            keyword_provider=provider,
        )
        return {
            "search_query": result.search_query,
            "keywords": result.keywords,
            "main_topics": result.main_topics,
            "context": result.context,
        }

    async def get_post(self, *, date_str: str) -> str | None:
        await self.ensure_indexed()
        for path in self.rag.iter_post_files():
            if path.stem == date_str:
                return path.read_text(encoding="utf-8")
        return None

    async def list_posts(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        directory = self.config.posts_dir
        if not directory.exists():
            return []

        files = sorted(
            self.rag.iter_post_files(), key=lambda path: path.stem, reverse=True
        )
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
            "total_posts": stats.total_posts,
            "total_chunks": stats.total_chunks,
            "persist_dir": str(stats.persist_dir),
            "vector_store": stats.vector_store,
        }

    async def reindex(self, *, force: bool = False) -> dict[str, int]:
        result = await asyncio.to_thread(self.rag.update_index, force_rebuild=force)
        return result


rag_server: RAGServer | None = None


@list_tools()
async def handle_list_tools() -> List[Tool]:  # type: ignore[valid-type]
    if MCP_IMPORT_ERROR is not None:
        raise RuntimeError(
            "O pacote 'mcp' não está instalado; instale-o para listar as tools."
        )

    return [
        Tool(
            name="search_posts",
            description=(
                "Busca trechos relevantes em posts anteriores usando "
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
                        "description": "Excluir posts dos últimos N dias (padrão: 7)",
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
                        "default": DEFAULT_KEYWORD_MODEL,
                    },
                },
                "required": ["transcripts"],
            },
        ),
        Tool(
            name="get_post",
            description="Retorna o conteúdo completo de uma post específica por data (YYYY-MM-DD).",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Data da post (YYYY-MM-DD)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    }
                },
                "required": ["date"],
            },
        ),
        Tool(
            name="list_posts",
            description="Lista posts disponíveis com paginação.",
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
            name="reindex_posts",
            description=(
                "Atualiza o índice do RAG processando posts novas ou modificadas. "
                "Use force=true para reindexar tudo."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Se true, reprocessa todas as posts",
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
        if name == "search_posts":
            hits = await rag_server.search_posts(**arguments)
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

        if name == "get_post":
            content = await rag_server.get_post(date_str=arguments["date"])
            if content:
                return [TextContent(type="text", text=content)]
            return [TextContent(type="text", text="Post não encontrada.")]

        if name == "list_posts":
            entries = await rag_server.list_posts(**arguments)
            markdown = format_post_listing(entries)
            return [TextContent(type="text", text=markdown)]

        if name == "get_rag_stats":
            stats = await rag_server.get_stats()
            lines = ["# Estatísticas do RAG\n"]
            for key, value in stats.items():
                lines.append(f"- **{key}**: {value}")
            return [TextContent(type="text", text="\n".join(lines))]

        if name == "reindex_posts":
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

    if not uri.startswith("post://"):
        raise ValueError(f"URI inválida: {uri}")

    date_str = uri.replace("post://", "")
    content = await rag_server.get_post(date_str=date_str)
    if content is None:
        raise ValueError(f"Post não encontrada: {date_str}")
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
