# CLI Moderno com Typer + Rich

A interface de linha de comando do Egrégora foi completamente migrada para
[Typer](https://typer.tiangolo.com/) com componentes de saída do
[Rich](https://rich.readthedocs.io/). O objetivo desta nota é documentar o estado
atual do CLI, facilitar a manutenção futura e evitar que resquícios do antigo
`argparse` voltem a aparecer.

---

## 🎯 Objetivos Atuais

- **Ergonomia** – comandos curtos com validações automáticas de tipo e mensagens
  claras de erro.
- **Feedback visual** – tabelas e painéis coloridos para listas, pré-visualização
  (dry-run) e resultados finais.
- **Descoberta guiada** – ajuda embutida (`--help`) e auto-complete de shell.
- **Reaproveitamento de configuração** – integração direta com
  `PipelineConfig` para carregar TOML ou usar defaults seguros.

---

## 🧱 Estrutura em `src/egregora/__main__.py`

O CLI expõe uma aplicação Typer instanciada como `app` e um `run()` usado pelo
entry point definido no `pyproject.toml`. Dois comandos de alto nível estão
presentes:

1. `process` (padrão) – executa o pipeline completo de newsletters.
2. `discover` – calcula identificadores anônimos para telefone ou apelido.

Trechos relevantes:

- Criação do aplicativo e opções compartilhadas (`ConfigFileOption`,
  `ZipsDirOption` etc.) fica concentrada em `src/egregora/__main__.py`.
- `_process_command` transforma os argumentos em uma instância de
  `PipelineConfig`, lidando com overrides e validação de timezone.
- O subcomando `discover` reaproveita `discover_identifier` e formata o
  resultado com `Panel`/`Table` do Rich.

---

## ⚙️ Comando `process`

Pode ser chamado explicitamente (`uv run egregora process`) ou implicitamente
(`uv run egregora`). Os principais parâmetros são:

| Opção                        | Descrição                                                                 |
|------------------------------|---------------------------------------------------------------------------|
| `--config, -c PATH`          | Carrega configurações de um TOML validado antes da execução.              |
| `--zips-dir PATH`            | Sobrescreve o diretório de exports do WhatsApp.                           |
| `--newsletters-dir PATH`     | Define a pasta de saída para newsletters geradas.                         |
| `--model NAME`               | Escolhe o modelo Gemini usado no resumo.                                  |
| `--timezone NAME`            | Timezone IANA aplicado para calcular datas de referência.                 |
| `--days N`                   | Limita a janela de dias recentes a processar.                             |
| `--disable-enrichment`/`--no-enrich` | Desativa o enriquecimento de links.                             |
| `--no-cache`                 | Ignora o cache persistente de enriquecimento.                             |
| `--list, -l`                 | Apenas lista os grupos detectados (real/virtual) em tabela Rich.          |
| `--dry-run`                  | Mostra um preview estruturado do que seria processado sem gerar arquivos. |

A coleta de grupos reais usa `group_discovery.discover_groups`, merges virtuais
são derivados de `PipelineConfig.merges`, e o dry-run retorna planos do tipo
`DryRunPlan` exibidos com painéis Rich (`src/egregora/processor.py`).

---

## 🔐 Comando `discover`

`uv run egregora discover "<valor>"` recebe um telefone ou apelido, detecta o
formato e devolve as três variantes (`human`, `short`, `full`). O fluxo interno
reutiliza `discover_identifier`, com tratamento de erros amigável e saída
formatada (veja `src/egregora/__main__.py`).

Uso típico:

```bash
uv run egregora discover "+55 11 91234-5678"
uv run egregora discover "apelido" --format short --quiet
```

---

## 🧭 Boas Práticas de Manutenção

- Centralize novas opções em `_process_command`; isso garante que tanto o
  comando padrão quanto o subcomando `process` permaneçam alinhados.
- Prefira componentes Rich (`Panel`, `Table`, `Console`) para qualquer saída que
  envolva listas, métricas ou mensagens de erro destacadas.
- Sempre adicione validações via callbacks do Typer (ex.: `_validate_config_file`
  para checar existência de TOML em `__main__.py`).
- Atualize este documento quando opções forem removidas/adicionadas para evitar
  regressões à versão `argparse`.

---

## 📌 Referências Rápidas

- Entry point oficial: `pyproject.toml` → `egregora = "egregora.__main__:run"`.
- Configuração padrão do pipeline: `PipelineConfig.with_defaults()` com suporte a
  merges virtuais e RAG opcional.
- Processamento unificado (real + virtual): `src/egregora/processor.py`.

Com Typer + Rich estabelecidos, o CLI está alinhado com a UX desejada e pronto
para evoluções incrementais sem a verbosidade do `argparse` original.
