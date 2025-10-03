# Content Enrichment Quickstart

Este guia mostra como ativar e validar rapidamente o sistema de enriquecimento de links no Egregora.

## 1. Preparação

1. Certifique-se de ter `uv` instalado e as dependências sincronizadas (`uv sync`).
2. Exporte a chave do Gemini:

   ```bash
   export GEMINI_API_KEY="sua-chave"
   ```

3. Garanta que existam arquivos `.zip` recentes em `data/whatsapp_zips/` (ou aponte outro diretório com `--zips-dir`).

## 2. Executando o exemplo

Para confirmar que o módulo funciona isoladamente:

```bash
python example_enrichment.py
```

O script usa um mini transcript com dois links e imprime a seção enriquecida que seria enviada ao prompt principal. Certifique-se de usar um modelo com suporte a URLs (`gemini-2.0-flash-exp`). Se a chave Gemini não estiver configurada o script continua e sinaliza que está operando offline.

## 2.1 Capacidades do sistema

O enriquecimento depende apenas do suporte nativo do Gemini:

- ✅ **Páginas web** — artigos, blogs, documentação.
- ✅ **PDFs** — processados diretamente via `Part.from_uri` (sem `pdfplumber`).
- ✅ **YouTube** — transcrição e análise automática, sem `yt-dlp`.
- ✅ **Imagens** — descrições e extração de detalhes com o Gemini multimodal.

> **Importante:** Nenhuma dependência externa é necessária; todo parsing é realizado pelo Gemini.

## 3. Pipeline com enriquecimento

Execute o comando abaixo para gerar uma newsletter de um dia com enriquecimento ativado e limiar de relevância 3:

```bash
uv run egregora --days 1 --relevance-threshold 3
```

Saída esperada (resumo):

```
[Enriquecimento] 4/6 itens relevantes processados em 42.1s.
[Resumo] Enriquecimento considerou 6 itens; 4 atenderam à relevância mínima de 3.
[OK] Newsletter criada em newsletters/2024-05-12.md usando dias 2024-05-12.
```

> **Dica:** Caso deseje desativar temporariamente, use `--disable-enrichment`.

## 4. Principais flags

| Flag | Descrição |
| --- | --- |
| `--relevance-threshold` | Nota mínima (1–5) para incluir um link no prompt. |
| `--max-enrichment-items` | Limite de links analisados por execução. |
| `--max-enrichment-time` | Tempo máximo (s) antes de cancelar o estágio. |
| `--enrichment-model` | Modelo Gemini usado para análise dos links. |
| `--enrichment-context-window` | Quantidade de mensagens antes/depois usadas como contexto. |
| `--analysis-concurrency` | Número de análises simultâneas do LLM. |
| `--cache-dir` | Define um diretório alternativo para o cache persistente. |
| `--disable-cache` | Executa o pipeline sem reutilizar análises anteriores. |
| `--cache-cleanup-days` | Remove entradas mais antigas que N dias ao iniciar. |

## 5. Boas práticas

- **Comece conservador**: limiar 3 e máximo de 20 itens para medir custo/benefício.
- **Observe os logs**: eles listam erros de análise do Gemini para cada link.
- **Monitore custos**: cada análise usa o modelo `enrichment_model`. Ajuste para versões mais baratas se necessário.
- **Tempo limite**: se muitos links falharem por timeout, aumente `max_enrichment_time` ou reduza `max_enrichment_items`.
- **Aproveite o cache**: mantenha o diretório `cache/` versionado para compartilhar resultados entre execuções e evitar custos repetidos.

## 6. Próximos passos

- Consulte `README.md` para visão geral do pipeline completo.
- Leia `CONTENT_ENRICHMENT_DESIGN.md` para detalhes de arquitetura, trade-offs e roadmap.
