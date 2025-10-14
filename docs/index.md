---
title: Egregora
description: Plataforma de inteligência para grupos WhatsApp com IA
hide:
  - navigation
  - toc
---

# Bem-vindo ao Egregora

<div class="grid cards" markdown>

-   :material-robot-happy:{ .lg .middle } __Inteligência Coletiva__

    ---

    Transforme conversas do WhatsApp em posts inteligentes com contexto histórico e perfis de participantes

    [:octicons-arrow-right-24: Começar](getting-started/index.md)

-   :material-brain:{ .lg .middle } __RAG Integrado__

    ---

    Busca semântica sobre todo histórico de conversas para contexto rico e continuidade narrativa

    [:octicons-arrow-right-24: Saiba mais](getting-started/rag-setup.md)

-   :material-book-open-variant:{ .lg .middle } __Blog & Releases__

    ---

    Acompanhe anúncios de versão e estudos de caso publicados com o pipeline 1.0

    [:octicons-arrow-right-24: Ler novidades](blog/index.md)

-   :material-shield-lock:{ .lg .middle } __Privacidade Garantida__

    ---

    Anonimização determinística mantém identidades seguras em todos os outputs

    [:octicons-arrow-right-24: Segurança](getting-started/first-post.md)

</div>

## Exemplo de Post Gerado

```markdown
---
title: "📩 Rationality Club — Diário de 2025-10-11"
date: 2025-10-11
authors:
  - egregora
categories:
  - daily
  - rationality-club
---

## Fio 1 — Retomando Debate sobre IA

Voltamos à questão da consciência artificial que iniciamos em 2025-03-15.
Member-ABCD trouxe sua perspectiva filosófica característica (Member-ABCD),
questionando os critérios fundamentais. Member-EFGH, com experiência em ML,
apresentou dados empíricos (Member-EFGH)...
```

## Recursos

<div class="grid" markdown>

=== "Pipeline Completo"

    ``` mermaid
    graph LR
      A[WhatsApp ZIP] --> B[Ingest (Polars)]
      B --> C[Anonymizer]
      C --> D[Gemini Embeddings]
      D --> E[DuckDB / FastMCP]
      E --> F[Jinja + Gemini]
      F --> G[MkDocs Build/Preview]
      F --> H[Internet Archive]
    ```

=== "Contexto Triplo"

    ```python
    context = PostContext(
        # Temporal
        rag_context="contextos históricos...",

        # Intelectual
        participant_profiles="expertise...",

        # Imediato
        transcript="mensagens de hoje..."
    )
    ```

</div>

## Estatísticas

<div class="grid" markdown>

!!! success "Eficiência"
    **70% redução** de custos com cache inteligente

!!! info "Qualidade"
    Posts com **contexto histórico + perfis**

!!! tip "Performance"
    **10x mais rápido** com cache aquecido

</div>

---

**Pronto para começar?**

[Instalar Egregora](getting-started/installation.md){ .md-button .md-button--primary }
[Ver Documentação](getting-started/index.md){ .md-button }
[Código Fonte :fontawesome-brands-github:](https://github.com/yourorg/egregora){ .md-button }
