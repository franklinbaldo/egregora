# Egregora

Automação para gerar newsletters diárias a partir de exports do WhatsApp usando o Google Gemini. Agora inclui um sistema opcional de **enriquecimento de conteúdos compartilhados**, capaz de resumir e contextualizar links citados nas conversas antes de gerar a newsletter.

> 📚 Para detalhes técnicos do fluxo de ponta a ponta, consulte as [Copilot Instructions](.github/copilot-instructions.md).

## 🌟 Principais recursos

- **Pipeline completo** para transformar arquivos `.zip` do WhatsApp em newsletters Markdown.
- **Integração com Gemini**: usa `google-genai` com configuração de segurança ajustada para conteúdos de grupos reais.
- **Enriquecimento de links**: identifica URLs e mídias e usa o suporte nativo do Gemini a `Part.from_uri` para analisá-los em paralelo com um modelo dedicado.
- **Sistema RAG integrado**: indexa newsletters anteriores para busca rápida via CLI ou MCP.
- **Perfis incrementais dos membros**: gera fichas analíticas por participante e atualiza automaticamente após cada newsletter.
- **Configuração flexível**: diretórios, fusos, modelos e limites ficam centralizados em `egregora.toml`, com overrides mínimos pela CLI.
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

1. Copie o arquivo de exemplo e ajuste conforme necessário:

   ```bash
   cp egregora.toml.example egregora.toml
   ```

2. Abra o arquivo e personalize as seções `[directories]`, `[pipeline]` e `[enrichment]` com os valores desejados.

3. Execute o pipeline apontando para o TOML:

   ```bash
   uv run egregora --config egregora.toml
   ```

Quer testar sem chamar o modelo? Use o modo de simulação:

```bash
uv run egregora --config egregora.toml --dry-run
```

### 🧪 Rodando os testes

1. Crie o ambiente virtual com `uv venv` (se ainda não existir).
2. Execute `uv sync` para instalar todas as dependências travadas — isso garante que bibliotecas opcionais como `polars` sejam baixadas automaticamente.
3. Rode a suíte desejada com `uv run --with pytest pytest`. Também é possível limitar o escopo, por exemplo:

   ```bash
   uv run --with pytest pytest tests/test_unified_processor_anonymization.py
   ```

## ✏️ Personalize o prompt do sistema

- Edite `src/egregora/prompts/system_instruction_base.md` para ajustar o tom padrão das newsletters (ou `egregora/prompts/system_instruction_base.md` em instalações via `pip`).
- Utilize `src/egregora/prompts/system_instruction_multigroup.md` para complementar instruções de grupos virtuais (ou `egregora/prompts/system_instruction_multigroup.md` no pacote instalado).
- Caso mantenha cópias personalizadas para produção, lembre-se de sincronizar qualquer alteração com o diretório de prompts instalado.

## 🖼️ Extração de Mídia

Além do enriquecimento de links, o Egregora agora extrai automaticamente mídias (imagens, vídeos, áudio) dos arquivos `.zip` do WhatsApp.

1.  **Extração**: Arquivos de mídia são salvos em `data/media/<slug-do-grupo>/media/<arquivo>` mantendo o nome original.
2.  **Substituição**: Marcadores como `IMG-20251003-WA0001.jpg (arquivo anexado)` viram links Markdown: `![IMG-20251003-WA0001.jpg](../../media/<slug-do-grupo>/media/IMG-20251003-WA0001.jpg)` na newsletter.
3.  **Preservação**: Cada grupo possui seu próprio diretório, evitando colisões mesmo em execuções diferentes.

> Dica: ao publicar via MkDocs, habilite o plugin `tools.mkdocs_media_plugin` (já configurado em `mkdocs.yml`) e defina `media_url_prefix = "/media"` no TOML para que os links apontem para o diretório público.

Essa funcionalidade garante que as mídias compartilhadas sejam acessíveis diretamente na newsletter gerada, enriquecendo ainda mais o contexto.

## 🔐 Privacidade por padrão

- **Anonimização determinística**: telefones e apelidos são convertidos em
  identificadores como `Member-ABCD` antes de qualquer processamento. Ajuste
  a seção `[anonymization]` no TOML caso precise desativar temporariamente.
- **Instruções rígidas ao LLM**: o prompt enviado ao Gemini reforça que nomes
  próprios, telefones e contatos diretos não devem aparecer na newsletter.
- **Revisão humana quando necessário**: para newsletters sensíveis, mantenha uma
  leitura final manual antes do envio.
- **Autodescoberta**: cada pessoa pode calcular o próprio identificador com
  `uv run egregora discover "<telefone ou apelido>"` ou consultar
  `docs/discover.md` para exemplos completos.

## 💾 Sistema de Cache

O Egregora mantém um cache persistente das análises de URLs para reduzir custos com API e acelerar execuções futuras. Por padrão o cache está habilitado e utiliza o diretório `cache/` versionado no repositório.

- Configure diretório, limpeza automática e limites através da seção `[cache]` no TOML.
- Defina `enabled = false` para desativar temporariamente.
- Ajuste `auto_cleanup_days` para controlar a retenção de análises antigas.

Também é possível acessar as estatísticas programaticamente:

```python
from pathlib import Path
from egregora.cache_manager import CacheManager

manager = CacheManager(Path("cache"))
print(manager.export_report())
```

Consulte `ENRICHMENT_QUICKSTART.md` para ver exemplos de execução e melhores práticas.

## 🧭 Estrutura padrão

- `data/whatsapp_zips/`: arquivos `.zip` exportados do WhatsApp (data opcional no nome).
- `data/daily/`: destino das newsletters geradas (`YYYY-MM-DD.md`).

As pastas são criadas automaticamente na primeira execução.

### Preparando exports do WhatsApp

1. Exporte sua conversa do WhatsApp como arquivo `.zip`
2. Coloque-o em `data/whatsapp_zips/`
3. **Opcional**: Renomeie com prefixo de data `YYYY-MM-DD-` para controle explícito

Exemplos de nomes aceitos:
- ✅ `Conversa do WhatsApp com Meu Grupo.zip` (detecta data automaticamente)
- ✅ `2025-10-03-Meu Grupo.zip` (data explícita)  
- ✅ `WhatsApp Chat with Team.zip` (detecta data automaticamente)

O sistema detecta datas automaticamente a partir do:
1. **Nome do arquivo** (se contém `YYYY-MM-DD`)
2. **Conteúdo das mensagens** (primeiras 20 linhas)
3. **Data de modificação** do arquivo (fallback)

## 🛠️ Uso via CLI

```bash
uv run egregora --config egregora.toml --days 2
```

O arquivo TOML concentra as opções avançadas. Use `--zips-dir` ou `--newsletters-dir` apenas para sobrescrever temporariamente os caminhos definidos na configuração.

Para inspecionar o plano antes de acionar o Gemini:

```bash
uv run egregora --config egregora.toml --dry-run
```

## 📬 Processamento de Backlog

Se você tem múltiplos dias de conversas para processar:

1. Coloque todos os zips em `data/whatsapp_zips/` (ou informe outro diretório).
2. Execute: `python scripts/process_backlog.py data/whatsapp_zips data/daily`
3. Use `--force` apenas se quiser sobrescrever newsletters já geradas.

O script simples usa o mesmo pipeline diário e imprime um resumo ao final. Para mais detalhes, veja [docs/backlog_processing.md](docs/backlog_processing.md)

## 🧪 Testes manuais

- Rode `python example_enrichment.py` para validar rapidamente o módulo de enriquecimento (define `GEMINI_API_KEY` antes para executar a análise com o LLM).
- Execute o comando principal com `--days 1` usando um exporto pequeno para validar o fluxo completo.

## 📚 Documentação complementar

- `ENRICHMENT_QUICKSTART.md` – visão geral + primeiros passos.
- `CONTENT_ENRICHMENT_DESIGN.md` – arquitetura completa e decisões de design.
- `PHILOSOPHY.md` – visão filosófica e motivações do projeto.

## 💡 Ideias Futuras

- Exportar newsletters e metadados para um formato colunar (ex.: Parquet) para facilitar análises históricas.
- Automatizar a geração de arquivos de arquivo/relatórios consolidando várias edições.

## 🔍 Sistema RAG (Retrieval-Augmented Generation)

O Egregora mantém um índice consultável de newsletters anteriores para recuperar
contexto relevante durante a geração de novas edições e em integrações com MCP.

**Características principais:**

- Busca semântica e por palavras-chave sobre o histórico de newsletters.
- Ferramentas MCP (`search_newsletters`, `list_newsletters`) para Claude e outros clientes.
- Suporte opcional a embeddings do Gemini para resultados mais ricos.
- Exportação opcional dos embeddings para Parquet, pronta para publicação como artefato no GitHub Actions ou Internet Archive (`export_embeddings` + `embedding_export_path`).

Consulte `docs/mcp-rag.md` e `docs/embeddings.md` para detalhes de uso e configuração.

## 🧠 Embeddings Modernos (Opcional)

Para elevar a qualidade das buscas do RAG, ative embeddings semânticos do Gemini.

```bash
uv run egregora --use-gemini-embeddings --embedding-dimension 768
```

Isso substitui o índice TF-IDF padrão por embeddings `gemini-embedding-001` com cache
persistente. A flag é opcional: se a API não estiver disponível o sistema volta ao TF-IDF.

## 👥 Perfis dos participantes

O Egregora pode manter perfis analíticos incrementais para cada membro do grupo.
Após gerar a newsletter diária, o pipeline reavalia quem participou, decide se o
perfil precisa ser atualizado e grava o resultado em dois formatos:

- `data/profiles/<uuid>.json`: dados estruturados para uso posterior;
- `docs/profiles/index.md`: índice em Markdown apontando para os JSONs públicos.

### Como habilitar

1. Certifique-se de que a chave `GEMINI_API_KEY` (ou `GOOGLE_API_KEY`) esteja configurada.
2. Ajuste a seção `[profiles]` no `egregora.toml`:

   ```toml
   [profiles]
   enabled = true
   profiles_dir = "data/profiles"
   profiles_docs_dir = "docs/profiles"
   min_messages = 2
   min_words_per_message = 15
   max_api_retries = 3
   minimum_retry_seconds = 30.0
   decision_model = "models/gemini-flash-latest"
   rewrite_model = "models/gemini-flash-latest"
   ```

3. Execute o pipeline normalmente. Cada participante que contribuir de forma
   significativa terá o perfil reavaliado e registrado.

Os perfis publicados ficam acessíveis em `docs/profiles/index.md`, com uma lista
clicável de todos os membros analisados. Esse arquivo é atualizado a cada execução,
facilitando o upload como artefato no GitHub Actions ou em outro repositório.

- `min_messages` / `min_words_per_message`: limites mínimos para considerar uma
  participação relevante no dia.
- `max_api_retries` / `minimum_retry_seconds`: controla retentativas quando o
  Gemini retorna `RESOURCE_EXHAUSTED` (rate limit) e o intervalo mínimo entre
  tentativas.

## 🤝 Contribuição

1. Faça fork do repositório e crie um branch.
2. Instale as dependências com `uv sync`.
3. Adicione testes ou atualize os exemplos conforme necessário.
4. Abra um PR descrevendo claramente as alterações.

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).
