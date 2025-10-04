# Egregora

Automação para gerar newsletters diárias a partir de exports do WhatsApp usando o Google Gemini. Agora inclui um sistema opcional de **enriquecimento de conteúdos compartilhados**, capaz de resumir e contextualizar links citados nas conversas antes de gerar a newsletter.

## 🌟 Principais recursos

- **Pipeline completo** para transformar arquivos `.zip` do WhatsApp em newsletters Markdown.
- **Integração com Gemini**: usa `google-genai` com configuração de segurança ajustada para conteúdos de grupos reais.
- **Enriquecimento de links**: identifica URLs e mídias e usa o suporte nativo do Gemini a `Part.from_uri` para analisá-los em paralelo com um modelo dedicado.
- **Sistema RAG integrado**: indexa newsletters anteriores para busca rápida via CLI ou MCP.
- **Configuração flexível**: diretórios, fuso horário, modelos e limites podem ser ajustados via CLI ou API.
- **Documentação extensa**: consulte `ENRICHMENT_QUICKSTART.md` e `CONTENT_ENRICHMENT_DESIGN.md` para aprofundar.

## 📦 Requisitos

- [Python](https://www.python.org/) 3.10 ou superior
- [uv](https://docs.astral.sh/uv/) para gerenciar dependências
- Variável `GEMINI_API_KEY` configurada com uma chave válida da API do Gemini

Dependências principais:

- `google-genai`

## 🚀 Instalação

1. Instale o `uv` (caso ainda não tenha):

   ```bash
   pip install uv
   ```

2. Sincronize as dependências do projeto:

   ```bash
   uv sync
   ```

3. Verifique se a variável `GEMINI_API_KEY` está presente no ambiente:

   ```bash
   export GEMINI_API_KEY="sua-chave"
   ```

## 🧠 Enriquecimento de conteúdos

O novo módulo de enriquecimento executa três etapas:

1. **Extração** – percorre os transcritos procurando URLs e marcadores de mídia (`<Mídia oculta>`), capturando até 3 mensagens de contexto antes/depois.
2. **Análise com Gemini** – envia cada referência para um modelo configurável que lê a URL diretamente e devolve resumo, pontos-chave, tom e relevância (1–5).
3. **Filtragem** – somente itens com relevância acima do limiar configurado entram no prompt final.

### Configuração rápida

```bash
uv run egregora --days 1 --relevance-threshold 3 --max-enrichment-items 20
```

Parâmetros úteis:

- `--enable-enrichment` / `--disable-enrichment`
- `--relevance-threshold` (1–5)
- `--max-enrichment-items`
- `--max-enrichment-time`
- `--enrichment-model`
- `--enrichment-context-window`
- `--analysis-concurrency`

## 🖼️ Extração de Mídia

Além do enriquecimento de links, o Egregora agora extrai automaticamente mídias (imagens, vídeos, áudio) dos arquivos `.zip` do WhatsApp.

1.  **Extração**: Arquivos de mídia são salvos no diretório `media/YYYY-MM-DD/`.
2.  **Substituição**: Marcadores como `IMG-20251003-WA0001.jpg (arquivo anexado)` são substituídos por links Markdown para a mídia extraída (ex: `![IMG-20251003-WA0001.jpg](media/2025-10-03/IMG-20251003-WA0001.jpg)`).
3.  **Preservação**: O nome do arquivo original é mantido para fácil referência.

Essa funcionalidade garante que as mídias compartilhadas sejam acessíveis diretamente na newsletter gerada, enriquecendo ainda mais o contexto.

## 🔐 Privacidade por padrão

- **Anonimização determinística**: telefones e apelidos são convertidos em
  identificadores como `User-ABCD` antes de qualquer processamento. Use
  `--disable-anonymization` apenas para depuração local.
- **Instruções rígidas ao LLM**: o prompt enviado ao Gemini reforça que nomes
  próprios, telefones e contatos diretos não devem aparecer na newsletter.
- **Revisão opcional**: habilite `--double-check-newsletter` para acionar uma
  segunda chamada ao LLM, que revisa e limpa a newsletter. É possível escolher um
  modelo dedicado com `--review-model` ou confiar na revisão humana.
- **Autodescoberta**: cada pessoa pode calcular o próprio identificador com
  `uv run egregora discover "<telefone ou apelido>"` ou consultar
  `docs/discover.md` para exemplos completos.

## 💾 Sistema de Cache

O Egregora mantém um cache persistente das análises de URLs para reduzir custos com API e acelerar execuções futuras. Por padrão o cache está habilitado e utiliza o diretório `cache/` versionado no repositório.

- Para escolher outro diretório, use `--cache-dir /caminho/para/cache`.
- Para desativar temporariamente, acrescente `--disable-cache` ao comando.
- Para remover entradas antigas, utilize `--cache-cleanup-days 90` (ou outro valor em dias).

Também é possível acessar as estatísticas programaticamente:

```python
from pathlib import Path
from egregora.cache_manager import CacheManager

manager = CacheManager(Path("cache"))
print(manager.export_report())
```

Consulte `ENRICHMENT_QUICKSTART.md` para ver exemplos de execução e melhores práticas.

## 🧭 Estrutura padrão

- `data/whatsapp_zips/`: arquivos `.zip` exportados do WhatsApp com a data no nome (`YYYY-MM-DD`).
- `newsletters/`: destino das newsletters geradas (`YYYY-MM-DD.md`).

As pastas são criadas automaticamente na primeira execução.

## 🛠️ Uso via CLI

```bash
uv run egregora \
  --zips-dir data/whatsapp_zips \
  --newsletters-dir newsletters \
  --group-name "RC LatAm" \
  --model gemini-flash-lite-latest \
  --days 2
```

Adicione as flags de enriquecimento conforme necessário. O CLI informa ao final quantos links foram processados e quantos atingiram o limiar de relevância.

## 📬 Processamento de Backlog

Se você tem múltiplos dias de conversas para processar:

1. Coloque todos os zips em `data/zips/`
2. Execute: `python scripts/process_backlog.py --scan`
3. Revise a estimativa de custos
4. Execute: `python scripts/process_backlog.py`

Para mais detalhes, veja [docs/backlog_processing.md](docs/backlog_processing.md)

## 🧪 Testes manuais

- Rode `python example_enrichment.py` para validar rapidamente o módulo de enriquecimento (define `GEMINI_API_KEY` antes para executar a análise com o LLM).
- Execute o comando principal com `--days 1` usando um exporto pequeno para validar o fluxo completo.

## 📚 Documentação complementar

- `ENRICHMENT_QUICKSTART.md` – visão geral + primeiros passos.
- `CONTENT_ENRICHMENT_DESIGN.md` – arquitetura completa e decisões de design.
- `PHILOSOPHY.md` – visão filosófica e motivações do projeto.
- `MIGRATION_GUIDE.md` – passos recomendados para atualizar entre versões.

## 🔍 Sistema RAG (Retrieval-Augmented Generation)

O Egregora mantém um índice consultável de newsletters anteriores para recuperar
contexto relevante durante a geração de novas edições e em integrações com MCP.

**Características principais:**

- Busca semântica e por palavras-chave sobre o histórico de newsletters.
- Ferramentas MCP (`search_newsletters`, `list_newsletters`) para Claude e outros clientes.
- Suporte opcional a embeddings do Gemini para resultados mais ricos.

Consulte `docs/mcp-rag.md` e `docs/embeddings.md` para detalhes de uso e configuração.

## 🧠 Embeddings Modernos (Opcional)

Para elevar a qualidade das buscas do RAG, ative embeddings semânticos do Gemini.

```bash
uv run egregora --use-gemini-embeddings --embedding-dimension 768
```

Isso substitui o índice TF-IDF padrão por embeddings `gemini-embedding-001` com cache
persistente. A flag é opcional: se a API não estiver disponível o sistema volta ao TF-IDF.

## 🤝 Contribuição

1. Faça fork do repositório e crie um branch.
2. Instale as dependências com `uv sync`.
3. Adicione testes ou atualize os exemplos conforme necessário.
4. Abra um PR descrevendo claramente as alterações.

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).
