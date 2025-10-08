# [EPIC] Migrar o pipeline de conteúdo para DataFrame-native (Polars Lazy + child tables + normalização Unicode + contrato de schema)

> **Status**: proposta  
> **Labels**: epic, area:pipeline, perf, breaking-change, dataframe-native  
> **Owners**: @<owner> · **Reviewers**: @<reviewers>  
> **Afeta**: `parser.py`, `transcript.py`, `enrichment.py`, `media_extractor.py`, `processor.py`, `pipeline.py`, `profiles/*`, `config/*`, `tests/*`, `docs/*`

## 🎯 Objetivo

Unificar todo o processamento de conteúdo em Polars de ponta a ponta, eliminando conversões DataFrame→texto→DataFrame, reduzindo tempo e memória, e consolidando um único fluxo com type safety e testabilidade superiores.

## 🔎 Contexto & Problema

Hoje coexistem dois mundos (DataFrame vs. texto), gerando:

- Conversões redundantes (50–200ms/dia/grupo), duplicação de lógica e perda de tipos.
- Regex em texto para tarefas que já possuem equivalentes vetorizados no Polars.
- `extract_transcript()` serve só para converter DF→texto e é reparseado depois.
- Orquestração dividida entre `pipeline.py` (legado) e `processor.py` (novo).

Isto foi mapeado em `CODE_ANALYSIS.md` como “esquizofrenia arquitetural”.

## ✅ Resultados esperados (Definition of Done)

1. Zero conversões DF↔texto no hot-path (texto só na renderização final).
2. ContentEnricher e MediaExtractor operando diretamente em Polars.
3. `processor.py` centraliza orquestração; `pipeline.py` deprecado (funções migradas).
4. Remoção de `extract_transcript()` (com mensagem clara de migração).
5. Ganho ≥ 30% no tempo por grupo/dia (bench marcado).
6. Redução ≥ 500 linhas de código duplicado.
7. Contrato de schema e normalização Unicode (evitar quebras de regex).
8. Testes passam e docs atualizadas (arquitetura, ADR, changelog, exemplos).

## 🔧 Escopo técnico (alto nível)

- Polars Lazy por padrão: do parser à etapa anterior à renderização (`pl.LazyFrame` + `collect()` nos checkpoints).
- Exprs vetorizadas (sem `map_elements`/loops) para URLs, mídia e contexto.
- Child tables: derivar `urls`/`media_refs` via `explode()`; manter `messages` como fato.
- Normalização Unicode (remoção de LRM/RTL, NFKC) antes de regex.
- Contrato de schema (timezone, tipos de data/horário, colunas obrigatórias).
- Boundary LLM: só converter linhas (ou refs) para objetos Python no ponto de chamada ao cliente (minimiza overhead).
- Renderer único de transcrição (texto só no final).
- Feature flag: TOML + ENV `EGREGORA_USE_DF_PIPELINE=1`.
- Sem `asyncio.run` em funções internas (apenas no entrypoint/CLI).

## 🧩 Alterações API (breaking)

- `transcript.extract_transcript(source, date)` **removido**.
  - Migração:
    ```python
    df = load_source_dataframe(source)
    df_day = df.filter(pl.col("date") == target_date)

    ContentEnricher.enrich_dataframe(df, target_dates, client)
    ```
- `ContentEnricher.enrich_dataframe(df, target_dates, client)` **adicionado**; `enrich(...)` (texto) deprecado e removido na v0.4.0.
- `MediaExtractor.find_attachment_names_dataframe(df)` e `replace_media_references_dataframe(df, ...)` **adicionados**.
- Renderer padronizado: `render_transcript(df_day, use_tagged=True|False)`.

## 📐 Contrato de schema

```python
MESSAGE_SCHEMA = {
  "timestamp": pl.Datetime("ns", "America/Porto_Velho"),
  "date": pl.Date,
  "author": pl.Utf8,
  "message": pl.Utf8,
  "original_line": pl.Utf8,
  "tagged_line": pl.Utf8,
}
```

Validação em runtime em pontos críticos (parser e pré-render).

## 🗺️ Plano de implementação (milestones)

### M1 — Enrichment DataFrame-native (sem romper legado)

- [ ] `enrichment.enrich_dataframe(...)` usando apenas exprs Polars:
  - [ ] Extração de URLs: `str.extract_all(URL_RE)` + `list.eval(pl.element().str.rstrip(...))`
  - [ ] Contexto (k): `shift()` (±1) ou `join` por range para janelas maiores.
  - [ ] Boundary: converter `urls_exploded` em `ContentReference` apenas na chamada LLM.
- [ ] `EnrichmentConfig.use_dataframe_pipeline` + override por ENV.
- [ ] Testes 1:1 (resultado e relevância) entre DF-path e texto (legado).
- [ ] `enrich()` marcado deprecated com docstring orientando migração.

### M2 — Media DataFrame-native

- [ ] `find_attachment_names_dataframe(df)` e `replace_media_references_dataframe(df, ...)` com exprs (`contains`/`replace_all`) e regex único por alternância.
- [ ] Normalização Unicode antes de regex (remover invisíveis; NFKC).

### M3 — Perfil/participação 100% DF

- [ ] `build_conversation(df)` vetorizado (`pl.format` + `dt.strftime`).
- [ ] `processor` usa somente DF para estatísticas/atualização.

### M4 — Orquestração unificada & remoções

- [ ] `processor` vira fonte de verdade; `pipeline.py` desmembrado:
  - [ ] Mover utilidades (descoberta de datas/ZIPs, ensure directories, seleção de janelas).
- [ ] Remover `extract_transcript()` e atualizar chamadas.
- [ ] Renderer único `render_transcript(df_day, use_tagged)` para newsletter.

### M5 — Benchmarks, métricas e limpeza

- [ ] Métricas no `Result` (shape in/out, `n_urls`, `n_media`, `duration_ms`, `rss_delta_mb`).
- [ ] `pytest-benchmark` com dataset sintético (≥ 500 msgs/50 URLs).
- [ ] Limpeza de código, remoção de duplicados, atualização de imports.

## 🧪 Plano de testes

- **Paridade funcional**:
  - [ ] Mesma contagem de itens/URLs entre DF e legado.
  - [ ] Contexto antes/depois preservado (janelas pequenas e grandes).
  - [ ] Substituição de mídia preserva schema e conteúdo.
- **Property-based (Hypothesis)**:
  - [ ] Mensagens com unicode invisível, nomes ambíguos (`IMG (1).jpg`), URLs com pontuação terminal, múltiplas por linha.
- **Benchmarks (`pytest-benchmark`)**:
  - [ ] Comparar DF-path vs texto (alvo: ≥ 30% mais rápido).
- **Snapshots** (golden files) para render de newsletter.
- **Tipos**: validação de schema + timezone no parser e pré-render.

## 📊 Métricas de sucesso

- Tempo total por grupo/dia: −30% (ou melhor).
- Memória de pico: −20%.
- Código removido/duplicado: ≥ 500 linhas.
- Flakiness de testes de enriquecimento: zero regressões.

## ⚠️ Riscos & mitigação

- Unicode invisível quebrando regex → normalização proativa + testes property-based.
- Cardinalidade alta de mídia → filtrar por `str.contains(pattern)` antes de `replace_all`.
- Quebra de downstream com remoção de `extract_transcript()` → deprecar numa release, remover na seguinte e prover guia de migração.
- TZ/Date mismatch em filtros → contrato de schema + casts explícitos.

## 📄 Documentação (obrigatória)

Atualizar e/ou criar:

- [ ] `README.md`:
  - [ ] Nova arquitetura (diagrama simples): Parser (Lazy) → Enrichment/Media (exprs) → Child tables → Renderer.
  - [ ] Como habilitar `use_dataframe_pipeline` via TOML e `EGREGORA_USE_DF_PIPELINE`.
  - [ ] Guia rápido de migração do legado (exemplos antes/depois).
- [ ] `CODE_ANALYSIS.md`:
  - [ ] Remover referência à “esquizofrenia” e registrar o estado unificado.
  - [ ] Explicar `LazyFrame`, pushdown e limites (quando `collect()`).
- [ ] ADR: `docs/adr/ADR-00X-dataframe-native.md`
  - [ ] Contexto, decisão (Polars Lazy + child tables + renderer final), alternativas rejeitadas (regex em texto), implicações, plano de reversão.
- [ ] `CONTRIBUTING.md`:
  - [ ] Padrões de schema, normalização Unicode, política de benchmarks, boundary LLM.
- [ ] `CHANGELOG.md`:
  - [ ] Deprecações (`enrich(text)`, `extract_transcript()`), remoção na v0.4.0.
- [ ] `egregora.toml.example`:
  - [ ] `use_dataframe_pipeline = true` + comentário sobre ENV override.
- [ ] Docstrings nos métodos novos com exemplos mínimos (copy-paste-ables).

## 📚 Guia de migração (snippet)

```diff
- transcript = extract_transcript(source, target_date)
- result = await enricher.enrich([(target_date, transcript)], client=client)
- attachments = MediaExtractor.find_attachment_names(transcript)
+ df = load_source_dataframe(source)
+ df_day = df.filter(pl.col("date") == target_date)
+ result = await enricher.enrich_dataframe(df_day, client=client)
+ attachments = MediaExtractor.find_attachment_names_dataframe(df_day)
+ transcript = render_transcript(df_day, use_tagged=source.is_virtual)
```

## 🧵 Tarefas (checklist executável)

### Código

- [ ] Parser retorna `LazyFrame` com date/TZ corretos.
- [ ] `enrichment.enrich_dataframe(...)` completo (URLs, contexto, boundary LLM).
- [ ] `media_extractor.*_dataframe(...)` completo (regex único, replace vetorizado).
- [ ] `profiles`: `build_conversation(df)` vetorizado.
- [ ] `processor`: orquestração única (sem `asyncio.run` interno).
- [ ] Remover `extract_transcript()` + renderer único.
- [ ] Migrar utilitários de `pipeline.py` para módulos corretos.

### Qualidade

- [ ] Validação de schema em pontos críticos.
- [ ] Normalização Unicode no ingresso do texto.
- [ ] Benchmarks com dataset sintético.
- [ ] Hypothesis + snapshots de newsletter.

### Documentação

- [ ] `README`, `CODE_ANALYSIS`, ADR, `CONTRIBUTING`, `CHANGELOG`, TOML example.
- [ ] Docstrings com exemplos curtos.

## 🔓 Critérios de aceite

- Benchmarks mostram ≥ 30% de melhora em tempo total (média de 5 runs) e ≥ 20% em memória de pico.
- Todos os testes (incluindo property-based e snapshots) passam.
- `pipeline.py` não é usado na orquestração; `processor` é fonte de verdade.
- Docs atualizadas e publicadas na árvore do repositório.
- `enrich(text)` marcado deprecated e coberto no `CHANGELOG`; `extract_transcript()` removido.

## 🔄 Rollout

- Habilitar por feature flag em canário (ex.: 1–2 grupos) via `EGREGORA_USE_DF_PIPELINE=1`.
- Monitorar métricas (`duration_ms`, `rss_delta_mb`, `n_urls`, `n_media`).
- Expandir a 100% após validação dos benchmarks e snapshots.

