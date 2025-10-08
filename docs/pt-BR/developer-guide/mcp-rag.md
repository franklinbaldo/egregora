# Servidor MCP para o RAG de Posts

O repositório inclui um servidor [Model Context Protocol (MCP)](https://www.anthropic.com/news/model-context-protocol)
que expõe as posts processadas pelo Egrégora como ferramentas de consulta.
Esta página descreve o estado atual da implementação, onde encontrar o código e
como executá-lo.

---

## 📦 Onde fica o servidor?

- **Arquivo principal**: `src/egregora/mcp_server/server.py`
- **Script de conveniência**: console script `egregora-mcp` (mapeia para `scripts/start_mcp_server.py`)
- **Configuração**: reutiliza `RAGConfig` via `PipelineConfig` ou TOML.

A função `main()` instancia `RAGServer`, carrega o índice vetorial (via
`PostRAG`) e inicia o loop MCP com `app.run_stdio()`.

---

## ⚙️ Como executar

1. Garanta que o pacote `mcp` esteja instalado (`uv add mcp`).
2. Habilite o RAG no `egregora.toml` (`[rag] enabled = true`) ou passe um TOML
   customizado com `--config`.
3. Execute o servidor:

```bash
uv run egregora-mcp --config egregora.toml
```

O script parseia `--config` e chama `asyncio.run(main(...))`.

A inicialização imprime logs indicando o carregamento do índice:

```
[MCP Server] Inicializando RAG...
[MCP Server] ✅ RAG inicializado
[MCP Server] Servidor pronto!
```

---

## 🧠 O que o servidor oferece

O decorador `@list_tools()` (`src/egregora/mcp_server/server.py`) registra seis
ferramentas MCP disponíveis para clientes como Claude Desktop.

| Tool                  | Função                                                                 |
|-----------------------|-------------------------------------------------------------------------|
| `search_posts`  | Busca semântica (top_k, min_similarity, exclude_recent_days).           |
| `generate_search_query` | Gera queries otimizadas a partir de transcritos de conversas.        |
| `get_post`      | Retorna o Markdown completo de uma data específica.                    |
| `list_posts`    | Lista posts com paginação (`limit`, `offset`).                   |
| `get_rag_stats`       | Resume contagem de posts, chunks e caminho do índice.            |
| `reindex_posts` | Reprocessa posts novas ou alteradas (com `force=true` opcional). |

Cada chamada é roteada por `handle_call_tool` (no mesmo arquivo), que formata a
resposta em Markdown antes de devolvê-la ao cliente.

Além das tools, o servidor expõe um resource `post://YYYY-MM-DD`, permitindo
que clientes leiam o conteúdo bruto através de `handle_read_resource`
(implementado em `server.py`).

---

## 🔁 Índice e Cache

- `RAGServer.ensure_indexed()` garante que o índice vetorial exista, criando-o
  sob demanda. O método usa `PostRAG`, que aplica `CachedGeminiEmbedding`
  com cache opcional em disco.
- A tool `reindex_posts` chama `PostRAG.update_index(force_rebuild=...)`
  e devolve estatísticas amigáveis.

---

## 🛡️ Tratamento de erros

- Se o pacote `mcp` não estiver disponível, o servidor aborta com mensagem clara
  durante `main()` ou quando as tools são listadas/chamadas.
- Requisições inválidas retornam mensagens ricas (ex.: "Tool desconhecida" ou
  `TextContent` com detalhes do erro).
- `handle_read_resource` valida URIs e acusa post ausente com exceção.


---

## 📌 Próximos passos sugeridos

1. Adicionar testes de integração simulando cliente MCP para garantir estabilidade.
2. Implementar autenticação básica (ex.: tokens locais) caso o servidor seja
   exposto em ambientes compartilhados.
3. Documentar exemplos de configuração para clientes populares (Claude Desktop,
   LlamaIndex MCP client, etc.).

A documentação anterior listava flags antigas e estruturas planejadas. Esta
versão reflete o servidor em produção, facilitando manutenção e onboarding.
