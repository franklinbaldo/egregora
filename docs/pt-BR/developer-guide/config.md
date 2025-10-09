# Configuração

Toda configuração do pipeline passa pela `PipelineConfig` (Pydantic).
Use o `egregora.toml` como fonte única e carregue via CLI ou Python.
Os campos mais usados são:

- **`[directories].zips_dir`** — padrão `data/whatsapp_zips`.
  Define onde ficam os exports ZIP aguardando processamento.
- **`[directories].posts_dir`** — padrão `data`.
  Diretório raiz dos posts gerados (diário/semanal/mensal).
- **`post_language`** — padrão `pt-BR`.
  Idioma padrão dos posts renderizados.
- **`default_post_author`** — padrão `egregora`.
  Assinatura usada no frontmatter de cada Markdown.
- **`[anonymization].enabled`** — padrão `true`.
  Liga ou desliga a substituição de autores.
- **`[anonymization].output_format`** — padrão `human`.
  Formato do identificador (`human`, `short`, `full`).
- **`[enrichment].enrichment_model`** — padrão `gemini-2.0-flash-exp`.
  Modelo usado para gerar resumos e links adicionais.
- **`[enrichment].max_concurrent_analyses`** — padrão `5`.
  Limite de chamadas paralelas ao LLM.
- **`[rag].enabled`** — padrão `false`.
  Ativa o índice vetorial usado pelo MCP e pelas buscas semânticas.
- **`[rag].top_k`** — padrão `5`.
  Quantidade de trechos retornados em cada busca.
- **`[cache].cache_dir`** — padrão `cache`.
  Raiz dos caches persistentes (enrichment, embeddings etc.).
- **`[profiles].enabled`** — padrão `true`.
  Gera perfis automáticos a partir do histórico recente.
- **`[remote_source].gdrive_url`** — padrão `None`.
  URL opcional de Google Drive para baixar novos ZIPs.

## Boas práticas

- Prefira editar apenas o `egregora.toml` e versioná-lo quando fizer ajustes
  permanentes.
- Em scripts Python, use `PipelineConfig.from_toml(Path("egregora.toml"))` para
  reaproveitar os mesmos valores.
- Combine flags: por exemplo, `[rag] enabled = true` junto com
  `[rag] export_embeddings = true` para publicar o Parquet no CI.
- Campos ausentes voltam para o padrão declarado na classe `PipelineConfig`.
  Consulte `src/egregora/config.py`.

## Exemplo completo

```toml
[directories]
zips_dir = "data/whatsapp_zips"
posts_dir = "data"

[anonymization]
output_format = "short"

[rag]
enabled = true
embedding_model = "models/gemini-embedding-001"
min_similarity = 0.6

[profiles]
max_profiles_per_run = 5
```

A partir deste arquivo você pode carregar a configuração em qualquer lugar:

```python
from pathlib import Path
from egregora.config import PipelineConfig

config = PipelineConfig.from_toml(Path("egregora.toml"))
```

Futuramente geraremos esta tabela diretamente da tipagem Pydantic — mantenha o
TOML como fonte da verdade para facilitar essa automação.
