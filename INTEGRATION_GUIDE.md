# Content Enrichment Integration Guide

Este guia resume as alterações necessárias para integrar o sistema de enriquecimento ao pipeline existente do Egregora. Ele presume que você já leu `ENRICHMENT_QUICKSTART.md` e tem familiaridade com a estrutura do projeto.

## 1. Visão geral

O módulo de enriquecimento adiciona uma etapa entre a leitura dos transcritos e a geração da newsletter. A partir da versão V2 a arquitetura foi simplificada para um único arquivo (`enrichment.py`) que usa o suporte nativo do Gemini para processar URLs, além dos ajustes em `pipeline.py`, `config.py` e `__main__.py`.

```
Transcritos -> [Enrichment] -> Prompt + Contexto -> Gemini -> Newsletter
```

## 2. Novos arquivos

Copie `enrichment.py` para `src/egregora/` (ou aplique os commits do repositório). O arquivo concentra a extração de referências e a análise com o Gemini via `Part.from_uri`, dispensando clientes HTTP próprios. Opcionalmente copie `example_enrichment.py` para executar testes manuais.

## 3. Dependências

Atualize `pyproject.toml` adicionando as bibliotecas necessárias e incremente a versão do projeto:

```toml
[project]
version = "0.2.0"
dependencies = [
    "google-genai>=0.3.0",
]
```

Rode `uv sync` após a alteração.

## 4. Configuração

Em `config.py` foi introduzido `EnrichmentConfig`, acoplado a `PipelineConfig`. Todos os parâmetros possuem valores padrão e podem ser ajustados via CLI.

Principais campos:

- `enabled`: ativa/desativa a etapa (padrão: `True`).
- `max_links`: máximo de links analisados por execução (padrão: 50).
- `relevance_threshold`: nota mínima para incluir no prompt (padrão: 2).
- `enrichment_model`: modelo Gemini para análise (padrão: `gemini-2.0-flash-exp`).
- `max_concurrent_analyses`: limite de requisições simultâneas ao Gemini (padrão: 5).
- `max_total_enrichment_time`: timeout global do estágio (padrão: 120s).

## 5. Ajustes no CLI (`__main__.py`)

Novas flags foram adicionadas:

- `--enable-enrichment` / `--disable-enrichment`
- `--relevance-threshold`
- `--max-enrichment-items`
- `--max-enrichment-time`
- `--enrichment-model`
- `--enrichment-context-window`
- `--analysis-concurrency`

Após gerar a newsletter o CLI imprime um resumo com a quantidade de itens processados e quantos atingiram o limiar configurado.

## 6. Alterações no pipeline

`pipeline.py` agora:

1. Instancia `ContentEnricher` quando `config.enrichment.enabled` é verdadeiro.
2. Executa `enricher.enrich(...)` antes de montar o prompt da newsletter.
3. Insere a seção retornada em `build_llm_input` via `enrichment_section`.
4. Registra estatísticas e erros no STDOUT.
5. Retorna `PipelineResult` com o campo adicional `enrichment` (instância de `EnrichmentResult`).

`build_llm_input` ganhou o parâmetro opcional `enrichment_section` que, quando presente, injeta o bloco `<<<ENRIQUECIMENTO_INICIO>>>` / `<<<ENRIQUECIMENTO_FIM>>>` no prompt.

## 7. Fluxo assíncrono

O enriquecimento roda com `asyncio` internamente. `pipeline.generate_newsletter` utiliza `asyncio.run` (com fallback para event loops já ativos) para coordenar as análises em paralelo. Ajuste `analysis_concurrency` conforme o ambiente para respeitar os limites de URLs do Gemini.

## 8. Testes e validação

1. Execute `python example_enrichment.py` para validar o módulo isoladamente.
2. Rode `uv run egregora --days 1` com um export real e observe os logs de enriquecimento.
3. Revise a newsletter resultante certificando-se de que a narrativa incorpora corretamente os links.

## 9. Troubleshooting

- **Tempo limite atingido**: aumente `max_enrichment_time` ou reduza `max_enrichment_items`.
- **Erros de DNS/SSL**: confira conectividade do servidor que executa o pipeline.
- **Gemini indisponível**: verifique `GEMINI_API_KEY` ou configure `--disable-enrichment` para seguir apenas com a newsletter.
- **Links repetidos ignorados**: o extrator deduplica por URL + remetente; ajuste o transcript se quiser repetir conscientemente.

## 10. Próximos passos

Consulte `CONTENT_ENRICHMENT_DESIGN.md` para explorar decisões de design, roadmap e sugestões de expansão (caching, análises bateladas, suporte a PDFs completos, etc.).
