# Pipeline DataFrame-native

Este documento consolida o estado atual da migração para um pipeline
100% DataFrame-native.
A meta é manter um fluxo único em Polars, do parser à renderização, evitando
conversões desnecessárias para texto durante o processamento.

## Objetivos

- Processar mensagens usando `pl.DataFrame` e `pl.LazyFrame` de ponta a ponta.
- Centralizar a orquestração em `processor.py`, mantendo o legado (`pipeline.py`)
  apenas como fachada enquanto durar a transição.
- Reduzir custos de CPU/memória eliminando reconstruções de transcript.
- Expor artefatos intermediários (links, mídia, métricas) como child tables
  derivadas do DataFrame principal.

## Backlog e ingestão

1. O script `scripts/process_backlog.py` carrega ZIPs de WhatsApp para
   `data/whatsapp_zips/`.
2. `parser.py` normaliza colunas (`timestamp`, `author`, `message`,
   `tagged_line`) já no formato Polars.
3. A pipeline identifica datas novas, aplica anonimização e grava os resultados
   em `data/<grupo>/posts/`.

Regras importantes:

- Normalize Unicode (`str.normalize('NFKC')`) antes de aplicar regex.
- Use `LazyFrame` nas transformações pesadas e chame `collect()` apenas ao
  renderizar o Markdown final.

## Enriquecimento

- `ContentEnricher` opera diretamente em DataFrames, extraindo URLs com
  `str.extract_all` e anexando contexto (`shift`/`join`).
- Cada rodada gera child tables: `urls`, `media_refs`, `highlights`.
  Prefira `explode()` para manter o schema simples.
- O módulo respeita `enrichment.max_concurrent_analyses` e grava métricas em
  `metrics/enrichment_run.csv` quando configurado.

## Renderização e publicação

- `render_post.py` recebe o DataFrame do dia/semana/mês e aplica templates
  Jinja.
- Mantenha o contrato de schema:
  - `timestamp`: `pl.Datetime("ns", "America/Porto_Velho")`
  - `date`: `pl.Date`
  - `author`: `pl.Utf8`
  - `message` e `tagged_line`: `pl.Utf8`
- Antes de publicar, rode `uv run egregora --days 1` e confirme que os posts caem
  em `docs/pt-BR/posts/...`.

## Próximos passos sugeridos

- Remover o flag `use_dataframe_pipeline` definitivamente (já padrão `True`).
- Adicionar testes de snapshot para comparar renderizações antigas vs. novas.
- Documentar benchmarks após cada otimização relevante.
- Integrar verificações de schema no CI para detectar regressões cedo.
