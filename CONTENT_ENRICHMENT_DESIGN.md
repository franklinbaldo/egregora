# Content Enrichment Design Document

> Última atualização: 2024-06-10 — versão V2 (Gemini com URLs nativas)

## 1. Objetivo

Adicionar ao Egregora uma etapa opcional de **enriquecimento de conteúdos** que analisa links e marcadores de mídia citados nas conversas antes de gerar a newsletter. A meta é fornecer contexto adicional ao modelo principal sem comprometer tempo de execução ou custo de maneira significativa.

## 2. Requisitos

### Funcionais

1. Detectar URLs e marcadores `<Mídia oculta>` nos transcritos.
2. Delegar ao Gemini a leitura das URLs via `Part.from_uri`, evitando parsing manual.
3. Analisar cada referência com um LLM rápido (Gemini Flash/2.0) retornando:
   - resumo curto;
   - até três pontos-chave acionáveis;
   - descrição do tom;
   - nota de relevância (1–5).
4. Incluir somente itens acima do limiar configurado na entrada do modelo principal.
5. Registrar erros de busca/análise sem interromper a geração da newsletter.

### Não funcionais

- **Tempo**: concluir em até 120 s (configurável) para ~50 links/dia.
- **Custo**: limitar-se a ~US$0.0002 por análise individual.
- **Resiliência**: falhas de rede ou do LLM não devem impedir a publicação.
- **Extensibilidade**: permitir inclusão futura de caching, parsing de PDFs e batch de LLM.

## 3. Arquitetura

```
┌───────────────────────────────────────────────┐
│ ContentEnricher                               │
│  ├─ extract_references() → ContentReference[] │
│  └─ analyze_with_gemini() → AnalysisResult    │
└───────────────────────────────────────────────┘
                     │
                     ▼
             ┌──────────────────┐
             │ Gemini (Part URI)│
             │  - Fetch remoto  │
             │  - Resposta JSON │
             └──────────────────┘
```

### 3.1 Principais estruturas

- **ContentReference**: representa uma menção a conteúdo no chat (URL, remetente, hora, contexto antes/depois).
- **AnalysisResult**: resumo estruturado pelo LLM (summary, key_points, tone, relevance, raw_response, error).
- **EnrichedItem**: combina referência + resultado da análise (ou erro).
- **EnrichmentResult**: agrega lista de itens, erros e duração.

## 4. Fluxo detalhado

1. `ContentEnricher.extract_references`
   - Regex `URL_RE` para http(s).
   - Regex `MEDIA_TOKEN_RE` para `<Mídia oculta>`.
   - Deduplica por (URL, remetente).
   - Usa `context_window` (default 3) para capturar mensagens vizinhas.

2. `ContentEnricher._analyze_reference`
   - Monta prompt JSON contendo contexto do chat.
   - Invoca `client.models.generate_content` anexando a URL via `types.Part.from_uri`.
   - Configura `response_mime_type="application/json"` e faz parse seguro com fallback para texto cru.
   - Converte em `AnalysisResult` com relevância padrão 1 em caso de erro.

3. `ContentEnricher.enrich`
   - Orquestra as etapas, respeitando `max_links` e `max_total_enrichment_time`.
   - Usa `asyncio.gather` com semáforo único para controlar chamadas paralelas ao Gemini.
   - Retorna `EnrichmentResult` + lista de erros humanos.
   - Formata seção com marcadores `<<<ENRIQUECIMENTO_INICIO/FIM>>>`.

5. `pipeline.generate_newsletter`
   - Executa enriquecimento (se habilitado) antes de montar o prompt principal.
   - Injeta a seção formatada e registra estatísticas.

## 5. Configuração e tuning

| Config | Descrição | Impacto |
| --- | --- | --- |
| `enabled` | ativa a etapa | bool global |
| `max_links` | limita número de links analisados | performance/custo |
| `relevance_threshold` | nota mínima para prompt | qualidade do contexto |
| `context_window` | mensagens antes/depois consideradas | preserva contexto |
| `max_concurrent_analyses` | chamadas simultâneas ao Gemini | custo/latência |
| `max_total_enrichment_time` | guarda-chuva de tempo total | SLAs |
| `enrichment_model` | modelo LLM usado (suporte a URLs obrigatório) | custo + fidelidade |

## 6. Considerações de custo

- Modelo recomendado: `gemini-2.0-flash-exp` (~US$0.0002/request) ou outro modelo com suporte oficial a URLs.
- Exemplo: 20 links/dia ⇒ ~US$0.004/dia ⇒ ~US$0.12/mês.
- Configurações econômicas:
  - aumentar `relevance_threshold` para 4;
  - limitar `max_links` para 15;
  - desativar completamente com `--disable-enrichment` quando necessário.

## 7. Falhas e mitigação

| Falha | Mitigação |
| --- | --- |
| URL não suportada/bloqueada pelo modelo | registrar erro e seguir; considerar fallback manual ou desativar enriquecimento. |
| Resposta inválida do LLM | fallback para resumo vazio e relevância 1. |
| Ausência de `GEMINI_API_KEY` | CLI alerta e recomenda desativar enriquecimento. |
| Limite de taxa do Gemini | reduzir `max_concurrent_analyses` ou distribuir execuções. |

## 8. Roadmap futuro

1. **Caching** de resultados (hash por URL) para evitar downloads repetidos.
2. **Extração completa de PDFs** usando `pdfplumber` (dependência opcional).
3. **Transcrições de YouTube** com `yt-dlp` para resumos mais ricos.
4. **Batching LLM**: agrupar múltiplos links numa só chamada quando suportado.
5. **Visão computacional**: descrição de imagens via modelos multimodais.
6. **Integração com banco de conhecimento**: armazenar resumos em base consultável.

## 9. Testes recomendados

- **Unitários**: extrator (regex + context window), parser JSON do Gemini, formatação da seção final.
- **Integração**: pipeline completo com transcripts reais e mocks de HTTP/LLM.
- **Smoke test**: `python example_enrichment.py` com variável de ambiente configurada.

## 10. Métricas sugeridas

- Tempo total do enriquecimento (`result.duration_seconds`).
- `# itens relevantes / # itens processados` por execução.
- Top N domínios mais frequentes (para decidir caching/whitelists).
- Erros recorrentes por tipo (timeout, DNS, SSL, JSON inválido).

## 11. Segurança e privacidade

- As URLs são requisitadas diretamente; o IP do servidor executor fica exposto aos sites acessados.
- Armazene logs com cuidado — podem conter links privados.
- Considere rodar atrás de proxies ou redes dedicadas se o grupo compartilhar conteúdos sensíveis.

## 12. Conclusão

O sistema de enriquecimento adiciona contexto valioso às newsletters com custo controlado. A arquitetura simplificada (enricher + Gemini) reduz manutenção e dependências, mantendo espaço para evoluções futuras como caching e suporte a novos tipos de mídia. O sucesso depende de monitorar relevância versus custo, ajustando limiares conforme o comportamento da comunidade.
