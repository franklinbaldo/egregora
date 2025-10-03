# Egregora — Manual Expandido

Egregora é um projeto comunitário que transforma exports de grupos do WhatsApp em newsletters diárias. O objetivo é tornar a inteligência coletiva acessível, contextualizada e buscável. Esta versão estendida do README descreve filosofia, arquitetura e fluxo operacional, complementando a documentação técnica disponível nos demais arquivos.

## 1. Visão

- **Propósito**: registrar conversas de grupo de forma honesta, contextualizada e útil.
- **Abordagem**: tratar a newsletter como voz coletiva — "nós" narrando nosso próprio dia.
- **Princípios**:
  - Transparência radical (links no ponto original, tensões explicitadas).
  - Respeito aos autores (atribuição por apelido ou final do telefone em cada frase).
  - Contexto acima de volume (organizar em fios com intenção narrativa).

## 2. Pipeline resumido

1. **Ingestão**: ler `.zip` exportados do WhatsApp (um por dia). Cada arquivo contém `.txt` com transcrições.
2. **Enriquecimento (opcional)**:
   - Extrai URLs e marcadores de mídia.
   - Envia cada link diretamente ao Gemini usando `Part.from_uri`, delegando o fetch para o próprio modelo (suporte a páginas, PDFs, YouTube etc.).
   - Analisa cada item com um modelo Gemini econômico, retornando resumo, pontos-chave, tom e relevância.
   - Só links relevantes entram no prompt principal.
3. **Geração**: enviar prompt estruturado ao Gemini responsável pela newsletter final.
4. **Saída**: escrever Markdown em `newsletters/YYYY-MM-DD.md`.

## 3. Componentes principais

- `src/egregora/pipeline.py`: orquestração do fluxo principal e integração com Gemini.
- `src/egregora/enrichment.py`: extração de referências e análise via Gemini (URLs nativas).
- `example_enrichment.py`: demonstração independente do enriquecimento.

## 4. Configuração

Crie um arquivo `.env` (ou exporte variáveis) com:

```bash
export GEMINI_API_KEY="sua-chave"
```

Opcionalmente configure diretórios e fuso horário via CLI ou utilizando `PipelineConfig.with_defaults()` na API Python.

### EnrichmentConfig

Parâmetros disponíveis (valores padrão entre parênteses):

| Campo | Descrição |
| --- | --- |
| `enabled` (True) | Ativa/desativa todo o estágio de enriquecimento. |
| `enrichment_model` (`gemini-2.0-flash-exp`) | Modelo usado para análise dos links. |
| `max_links` (50) | Máximo de referências processadas por execução. |
| `context_window` (3) | Mensagens antes/depois usadas como contexto. |
| `relevance_threshold` (2) | Nota mínima para incluir o item no prompt. |
| `max_concurrent_analyses` (5) | Análises LLM simultâneas. |
| `max_total_enrichment_time` (120s) | Tempo total reservado à etapa. |

## 5. Fluxo operacional

1. **Preparar dados**: coloque os `.zip` em `data/whatsapp_zips/` com datas corretas.
2. **Executar pipeline**:

   ```bash
   uv run egregora --days 2 --relevance-threshold 3
   ```

3. **Verificar logs**: a CLI informa o status do enriquecimento (quantos itens foram processados e quantos atingiram o limiar).
4. **Revisar newsletter**: arquivo Markdown gerado em `newsletters/`.

## 6. Estratégias de custo e desempenho

- **Modelos**: use `gemini-2.0-flash-exp` (ou outro com suporte a URLs) para análise; troque por versões experimentais conforme orçamento.
- **Limites**: ajuste `max_links` e `relevance_threshold` conforme volume do grupo.
- **Cache (futuro)**: camada sugerida no design (`CONTENT_ENRICHMENT_DESIGN.md`) para evitar downloads repetidos.
- **Batching**: planejado para reduzir o número de chamadas ao LLM analisador.

## 7. Roadmap resumido

- Extração de transcritos do YouTube (`yt-dlp`).
- Leitura de PDFs com `pdfplumber`.
- Caching local ou Redis.
- Análise batelada de links.
- Integração com APIs de visão para descrever imagens e vídeos curtos.

## 8. Contribuindo

1. Abra uma issue descrevendo o problema ou proposta.
2. Discuta com a comunidade no repositório ou grupo.
3. Desenvolva em um branch dedicado, com commits descritivos.
4. Atualize a documentação relevante (design, integração, quickstart).
5. Envie PR incluindo resultados de testes manuais ou automatizados.

## 9. Recursos adicionais

- `ENRICHMENT_QUICKSTART.md`: passo a passo prático.
- `INTEGRATION_GUIDE.md`: diffs e instruções para incorporar o módulo em sistemas existentes.
- `CONTENT_ENRICHMENT_DESIGN.md`: decisões arquiteturais, diagramas e análises de custo.

---

**Egregora** é um experimento contínuo em curadoria coletiva. Use, adapte e compartilhe melhorias!
