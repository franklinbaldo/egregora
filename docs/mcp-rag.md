# MCP Server para RAG de Newsletters

## 📋 Visão Geral

O repositório inclui um **MCP (Model Context Protocol) server local** que expõe o sistema RAG como serviço, permitindo:

1. **Claude Desktop** buscar contexto histórico durante conversas
2. **Pipeline Egregora** consumir RAG via protocolo padronizado
3. **Desenvolvedores** testar e debugar queries facilmente
4. **Outras ferramentas** integrar com o RAG

**Vantagem principal:** Separação de responsabilidades + interface padronizada.

### Status atual (2025-10-03)

- ✅ Servidor MCP funcional em `src/egregora/mcp_server/server.py`.
- ✅ Ferramentas expostas: `search_newsletters`, `list_newsletters`, `get_newsletter`.
- ✅ Integração direta com o `NewsletterRAG` e cache persistente.
- 🔄 Suporte opcional a embeddings do Gemini (`--use-gemini-embeddings`).
- 🧪 Testes automatizados planejados (`test_mcp_server.py`).

---

## 🎯 O Que é MCP?

**Model Context Protocol** - Protocolo da Anthropic para conectar LLMs a fontes de dados:

```
┌─────────────┐         ┌─────────────┐         ┌──────────────┐
│ Claude      │  ←MCP→  │ MCP Server  │  ←─→    │ Data Source  │
│ Desktop     │         │ (Local)     │         │ (Newsletters)│
└─────────────┘         └─────────────┘         └──────────────┘
```

**Features MCP:**
- ✅ Protocolo padrão (JSON-RPC)
- ✅ Tools (funções que Claude pode chamar)
- ✅ Resources (dados que Claude pode ler)
- ✅ Prompts (templates reutilizáveis)

---

## 🏗️ Arquitetura Proposta

### Componentes

```
egregora/
├── src/
│   └── egregora/
│       ├── rag/
│       │   ├── __init__.py
│       │   ├── core.py              # Núcleo do RAG (sem dependência MCP)
│       │   ├── indexer.py           # Indexação incremental
│       │   ├── search.py            # Busca e ranqueamento
│       │   └── query_gen.py         # Geração automática de queries
│       ├── mcp_server/
│       │   ├── __init__.py
│       │   ├── server.py            # Servidor MCP
│       │   ├── tools.py             # Definição das tools
│       │   └── config.py            # Configuração do server
│       └── pipeline.py              # Integração com o RAG/MCP
└── scripts/
    └── start_mcp_server.py          # Script auxiliar para desenvolvimento
```

### Separação de Responsabilidades

**1. Core RAG (independente de MCP):**
- Indexação incremental
- Geração de embeddings
- Busca semântica
- Query inteligente
- Cache em disco

**2. MCP Server (camada de interface):**
- Expor RAG via protocolo MCP
- Tools para Claude chamar
- Resources para ler newsletters
- Validação de requests

**Embeddings do Gemini**
- Ative via `RAGConfig(use_gemini_embeddings=True)` ou flag CLI `--use-gemini-embeddings`.
- O servidor MCP utiliza automaticamente o índice configurado (TF-IDF ou embeddings).
- Cache persistente em `cache/embeddings/` garante custos previsíveis.

**3. Pipeline (MCP client):**
- Conectar ao MCP server
- Chamar tools via protocolo
- Integração transparente

---

## 🔧 Implementação do MCP Server

### Arquivo: `src/egregora/mcp_server/server.py`

```python
"""
MCP Server para RAG de newsletters.

Expõe o sistema RAG via Model Context Protocol,
permitindo que Claude e outras ferramentas busquem
contexto histórico de newsletters anteriores.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import date

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Resource,
    ResourceTemplate,
)

from ..rag.index import NewsletterRAG
from ..rag.query_gen import QueryGenerator
from ..config import RAGConfig

# Inicializar server
app = Server("egregora-rag")


class RAGServer:
    """Wrapper do RAG para MCP server."""
    
    def __init__(self, config_path: Path | None = None):
        # Carregar config
        if config_path and config_path.exists():
            import tomli
            with open(config_path, 'rb') as f:
                config_dict = tomli.load(f)
            self.config = RAGConfig(**config_dict.get('rag', {}))
        else:
            self.config = RAGConfig()
        
        # Inicializar RAG
        self.rag = NewsletterRAG(
            newsletters_dir=Path("data/daily"),
            cache_dir=Path("cache/rag"),
            config=self.config,
        )
        
        # Query generator
        self.query_gen = QueryGenerator(self.config)
        
        # Lazy loading de índice
        self._indexed = False
    
    async def ensure_indexed(self):
        """Garante que índice está carregado."""
        if not self._indexed:
            await asyncio.to_thread(self.rag.load_index)
            self._indexed = True
    
    async def search_newsletters(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
        exclude_recent_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Busca trechos relevantes."""
        await self.ensure_indexed()
        
        results = await asyncio.to_thread(
            self.rag.search,
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
            exclude_recent_days=exclude_recent_days,
        )
        
        return [
            {
                "text": chunk.text,
                "date": chunk.newsletter_date.isoformat(),
                "section": chunk.section_title,
                "similarity": score,
                "path": str(chunk.newsletter_path),
            }
            for chunk, score in results
        ]
    
    async def generate_query(
        self,
        transcripts: str,
        model: str = "gemini-2.0-flash-exp",
    ) -> Dict[str, Any]:
        """Gera query inteligente dos transcritos."""
        query_data = await asyncio.to_thread(
            self.query_gen.generate,
            transcripts=transcripts,
            model=model,
        )
        return query_data
    
    async def get_newsletter(self, date_str: str) -> Optional[str]:
        """Retorna conteúdo completo de uma newsletter."""
        await self.ensure_indexed()
        
        try:
            newsletter_date = date.fromisoformat(date_str)
            newsletter_path = Path("data/daily") / f"{date_str}.md"
            
            if newsletter_path.exists():
                return newsletter_path.read_text(encoding="utf-8")
        except (ValueError, OSError):
            pass
        
        return None
    
    async def list_newsletters(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, str]]:
        """Lista newsletters disponíveis."""
        newsletters_dir = Path("data/daily")
        
        if not newsletters_dir.exists():
            return []
        
        # Listar e ordenar por data (mais recente primeiro)
        files = sorted(
            newsletters_dir.glob("*.md"),
            key=lambda p: p.stem,
            reverse=True,
        )
        
        # Paginação
        paginated = files[offset:offset + limit]
        
        return [
            {
                "date": f.stem,
                "path": str(f),
                "size_kb": f.stat().st_size // 1024,
            }
            for f in paginated
        ]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do RAG."""
        await self.ensure_indexed()
        
        return await asyncio.to_thread(self.rag.get_stats)
    
    async def reindex(self, force: bool = False) -> Dict[str, int]:
        """Reindexar newsletters."""
        return await asyncio.to_thread(
            self.rag.update_index,
            force_rebuild=force,
        )


# Instância global
rag_server: Optional[RAGServer] = None


@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Lista tools disponíveis no servidor."""
    
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
                        "description": "Query de busca (pode ser pergunta, tópicos, keywords)"
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
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="generate_search_query",
            description=(
                "Gera uma query de busca otimizada a partir de transcritos "
                "de conversas. Usa LLM para identificar tópicos principais."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "transcripts": {
                        "type": "string",
                        "description": "Texto dos transcritos a analisar"
                    },
                    "model": {
                        "type": "string",
                        "description": "Modelo LLM a usar (padrão: gemini-2.0-flash-exp)",
                        "default": "gemini-2.0-flash-exp",
                    }
                },
                "required": ["transcripts"],
            },
        ),
        Tool(
            name="get_newsletter",
            description=(
                "Retorna o conteúdo completo de uma newsletter específica "
                "por data (formato YYYY-MM-DD)."
            ),
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
                    }
                },
            },
        ),
        Tool(
            name="get_rag_stats",
            description="Retorna estatísticas do sistema RAG (chunks, cache, etc).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="reindex_newsletters",
            description=(
                "Reconstrói o índice do RAG e informa quantas newsletters e "
                "chunks foram processados. Use force=true para reindexar tudo."
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


@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handler para chamadas de tools."""
    
    global rag_server
    
    if rag_server is None:
        return [TextContent(
            type="text",
            text="Erro: RAG server não inicializado"
        )]
    
    try:
        if name == "search_newsletters":
            results = await rag_server.search_newsletters(**arguments)
            
            # Formatar resultados
            output = ["# Trechos Relevantes de Newsletters Anteriores\n"]
            
            for i, result in enumerate(results, 1):
                output.append(f"## Trecho {i} — {result['date']} "
                            f"(relevância: {result['similarity']:.0%})")
                if result['section']:
                    output.append(f"*{result['section']}*\n")
                output.append(result['text'])
                output.append("\n---\n")
            
            return [TextContent(type="text", text="\n".join(output))]
        
        elif name == "generate_search_query":
            query_data = await rag_server.generate_query(**arguments)
            
            output = [
                "# Query Gerada\n",
                f"**Tópicos Principais:** {', '.join(query_data['main_topics'])}\n",
                f"**Keywords:** {', '.join(query_data['keywords'])}\n",
                f"\n**Query de Busca:**\n{query_data['search_query']}\n",
                f"\n**Contexto:**\n{query_data['context']}",
            ]
            
            return [TextContent(type="text", text="\n".join(output))]
        
        elif name == "get_newsletter":
            content = await rag_server.get_newsletter(arguments["date"])
            
            if content:
                return [TextContent(type="text", text=content)]
            else:
                return [TextContent(
                    type="text",
                    text=f"Newsletter não encontrada: {arguments['date']}"
                )]
        
        elif name == "list_newsletters":
            newsletters = await rag_server.list_newsletters(**arguments)
            
            output = ["# Newsletters Disponíveis\n"]
            for nl in newsletters:
                output.append(f"- {nl['date']} ({nl['size_kb']} KB)")
            
            return [TextContent(type="text", text="\n".join(output))]
        
        elif name == "get_rag_stats":
            stats = await rag_server.get_stats()

            output = [
                "# Estatísticas do RAG\n",
                f"**Total de Newsletters:** {stats['total_newsletters']}",
                f"**Total de Chunks:** {stats['total_chunks']}",
                f"**Vector Store:** {stats['vector_store']}",
                f"**Persistência:** {stats['persist_dir']}",
            ]

            return [TextContent(type="text", text="\n".join(output))]
        
        elif name == "reindex_newsletters":
            result = await rag_server.reindex(**arguments)

            output = [
                "# Reindexação Concluída\n",
                f"- Newsletters processadas: {result['newsletters_count']}",
                f"- Chunks indexados: {result['chunks_count']}",
            ]

            return [TextContent(type="text", text="\n".join(output))]
        
        else:
            return [TextContent(
                type="text",
                text=f"Tool desconhecido: {name}"
            )]
    
    except Exception as e:
        import traceback
        error_msg = f"Erro ao executar {name}: {str(e)}\n\n{traceback.format_exc()}"
        return [TextContent(type="text", text=error_msg)]


@app.list_resources()
async def handle_list_resources() -> List[Resource]:
    """Lista resources disponíveis (newsletters)."""
    
    global rag_server
    
    if rag_server is None:
        return []
    
    newsletters = await rag_server.list_newsletters(limit=100)
    
    return [
        Resource(
            uri=f"newsletter://{nl['date']}",
            name=f"Newsletter {nl['date']}",
            description=f"Newsletter do dia {nl['date']} ({nl['size_kb']} KB)",
            mimeType="text/markdown",
        )
        for nl in newsletters
    ]


@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Lê conteúdo de um resource."""
    
    global rag_server
    
    if not uri.startswith("newsletter://"):
        raise ValueError(f"URI inválida: {uri}")
    
    date_str = uri.replace("newsletter://", "")
    
    content = await rag_server.get_newsletter(date_str)
    
    if content is None:
        raise ValueError(f"Newsletter não encontrada: {date_str}")
    
    return content


async def main():
    """Inicia o MCP server."""
    
    global rag_server
    
    # Inicializar RAG server
    print("[MCP Server] Inicializando RAG...")
    rag_server = RAGServer()
    print("[MCP Server] ✅ RAG inicializado")
    
    # Rodar server
    print("[MCP Server] Servidor pronto!")
    print("[MCP Server] Aguardando conexões...")
    
    async with app.run_stdio():
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📝 Configuração do Claude Desktop

### Arquivo: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "egregora-rag": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/caminho/para/egregora",
        "python",
        "-m",
        "egregora.mcp_server.server"
      ],
      "env": {
        "GEMINI_API_KEY": "sua-api-key-aqui"
      }
    }
  }
}
```

---

## 🔌 Integração no Pipeline

### Modificar `pipeline.py` para usar MCP client

```python
"""Pipeline usando MCP client para RAG."""

from mcp.client import Client, StdioServerParameters

async def generate_newsletter_with_rag(
    config: PipelineConfig,
    ...
) -> PipelineResult:
    
    # ... código existente ...
    
    # Conectar ao MCP server
    if config.rag.enabled:
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "egregora.mcp_server.server"],
            env={"GEMINI_API_KEY": os.environ["GEMINI_API_KEY"]}
        )
        
        async with Client() as client:
            # Iniciar servidor
            await client.connect(server_params)
            
            # 1. Gerar query inteligente
            transcripts_sample = prepare_transcripts_sample(sanitized_transcripts)
            
            query_result = await client.call_tool(
                "generate_search_query",
                arguments={"transcripts": transcripts_sample}
            )
            
            # 2. Buscar trechos relevantes
            search_result = await client.call_tool(
                "search_newsletters",
                arguments={
                    "query": query_data['search_query'],
                    "top_k": config.rag.top_k,
                    "min_similarity": config.rag.min_similarity,
                }
            )
            
            # 3. Adicionar ao prompt
            rag_context = search_result[0].text
    
    # ... resto do código ...
```

---

## 🎯 Casos de Uso

### 1. **Claude Desktop - Chat Interativo**

```
Usuário: O que já discutimos sobre privacidade em IA?

Claude: [chama search_newsletters com query "privacidade IA"]

Claude: Encontrei 3 discussões relevantes:

1. **2025-09-15** (87% relevante)
   Debatemos sobre uso de dados pessoais em modelos de IA...
   
2. **2025-09-20** (82% relevante)
   Discutimos conformidade com LGPD...

...
```

### 2. **Pipeline Egregora - Geração Au
