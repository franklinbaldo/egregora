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

    [:octicons-arrow-right-24: Saiba mais](guides/rag.md)

-   :material-account-group:{ .lg .middle } __Perfis Intelectuais__

    ---

    Sistema rastreia expertise, estilo de pensamento e evolução de cada participante

    [:octicons-arrow-right-24: Ver perfis](guides/profiles.md)

-   :material-shield-lock:{ .lg .middle } __Privacidade Garantida__

    ---

    Anonimização determinística mantém identidades seguras em todos os outputs

    [:octicons-arrow-right-24: Segurança](guides/privacy.md)

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
      A[WhatsApp ZIP] --> B[Parser]
      B --> C[Anonymizer]
      C --> D[Enriquecimento]
      D --> E[Generator + RAG]
      E --> F[Post Markdown]
      F --> G[MkDocs Site]
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
[Ver Documentação](guides/index.md){ .md-button }
[Código Fonte :fontawesome-brands-github:](https://github.com/yourorg/egregora){ .md-button }
