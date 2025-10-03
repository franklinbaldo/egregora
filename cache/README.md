# Cache de Análises do Egregora

Este diretório armazena as análises persistentes de URLs enriquecidas pelo pipeline.

## Estrutura

- `index.json`: índice com metadados de todas as análises.
- `analyses/`: arquivos JSON completos organizados por mês (`YYYY-MM`).
- `stats.json`: métricas agregadas de uso do cache.

## Manutenção

Para limpar entradas não utilizadas há mais de 90 dias:

```bash
uv run egregora --cache-cleanup-days 90
```

Para desativar o cache durante uma execução:

```bash
uv run egregora --disable-cache
```

Para inspecionar as estatísticas atuais programaticamente:

```python
from pathlib import Path
from egregora.cache_manager import CacheManager

manager = CacheManager(Path("cache"))
print(manager.get_stats())
```

## Versionamento

✅ Deve ser versionado: `index.json`, `stats.json`, `analyses/**/*.json`
❌ Deve ser ignorado: arquivos temporários (`*.tmp`, `*.lock`)
