# Processamento de Backlog

Este guia descreve como usar os utilitários de backlog para transformar vários dias de conversas do WhatsApp em newsletters diárias.

## Visão Geral

O fluxo de backlog usa o `BacklogProcessor` para:

1. Mapear arquivos `.zip` pendentes.
2. Estimar custos e tempo de processamento.
3. Processar cada dia sequencialmente com checkpoint automático.
4. Retomar execuções interrompidas sem perder progresso.

## Pré-requisitos

- Arquivos `.zip` do WhatsApp nomeados com a data (ex.: `2024-10-01.zip`).
- `GEMINI_API_KEY` configurada no ambiente.
- Dependências instaladas (`uv sync`).

## Estrutura de Arquivos

```
project/
├── data/
│   └── zips/
│       ├── 2024-10-01.zip
│       └── 2024-10-02.zip
├── docs/
│   └── reports/
│       └── daily/
└── cache/
    └── backlog_checkpoint.json
```

## Script Principal (`scripts/process_backlog.py`)

### Escanear pendências

```bash
python scripts/process_backlog.py --scan
```

Exemplo de saída:

```
📊 Análise de Backlog
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total de zips encontrados: 12
Newsletters já existentes: 4
Dias pendentes: 8

Período: 2024-08-15 até 2024-08-26

Estatísticas estimadas:
- Total de mensagens: ~1.540
- Total de URLs: ~120
- Tempo estimado: ~85.0 min
- Custo estimado: $1.54 USD
```

### Processar dias

```bash
python scripts/process_backlog.py --start-date 2024-08-15 --max-per-run 3
```

Opções importantes:

- `--resume`: retoma do último checkpoint.
- `--dry-run`: simula o processamento sem gerar newsletters.
- `--skip-enrichment`: pula enriquecimento de URLs para reduzir custo.
- `--force-rebuild`: reprocessa mesmo se a newsletter existir.
- `--max-per-run N`: limita a quantidade processada em uma única execução.

## Relatórios (`scripts/backlog_report.py`)

Gerar relatório resumido:

```bash
python scripts/backlog_report.py
```

Gerar relatório detalhado com exportação JSON:

```bash
python scripts/backlog_report.py --detailed --output report.json
```

## Checkpoints

O arquivo `cache/backlog_checkpoint.json` é atualizado automaticamente após cada dia. Ele inclui:

- `last_processed_date`: último dia concluído.
- `total_processed`: total acumulado de dias processados.
- `total_pending`: estimativa de pendências restantes.
- `failed_dates`: lista de dias com falha.
- `statistics`: métricas da última execução (mensagens, tempo, custo estimado).

Para reiniciar do zero, exclua o arquivo de checkpoint e execute o script novamente.

## Troubleshooting

- **Erro de API ou rate limit:** o processador aplica backoff exponencial automaticamente. Ajuste `processing.max_retries` e `processing.delay_between_days` em `scripts/backlog_config.yaml`.
- **Arquivos corrompidos:** o scanner ignora `.zip` sem data válida ou com erro de leitura. Verifique o arquivo manualmente.
- **Custos elevados:** use `--skip-enrichment` e processe em lotes menores com `--max-per-run`.

## Configuração Avançada

Personalize `scripts/backlog_config.yaml` para ajustar delays, timeout, logging e checkpoints. Para usar outro arquivo de configuração, passe `--config caminho/config.yaml` ao chamar o script.

## FAQ

**Posso processar múltiplos dias em paralelo?**
: O pipeline atual é sequencial para simplificar rate limiting. Para grandes volumes, execute em lotes menores.

**Como saber o progresso durante a execução?**
: Monitore os logs em `cache/backlog_processing.log` ou execute `python scripts/backlog_report.py` em outro terminal.

**Posso reprocessar um dia específico?**
: Use `--force-rebuild` e filtre o intervalo com `--start-date`/`--end-date`.

---

Pronto! Agora você pode manter o backlog em dia com segurança e previsibilidade.
