---
hide:
  - navigation
  - toc
---

# Egregora

<div class="md-hero" style="text-align: center; padding: 2rem 0;">
  <h1>Egregora</h1>
  <p style="font-size: 1.5rem; font-weight: 300;">The LLM-Era Yahoo Pipes<br>Composable AI Agents for Personal Knowledge Feeds</p>
  <div style="margin-top: 1rem;">
    <span class="md-tag" style="font-size: 0.9rem; padding: 4px 8px; border: 1px solid currentColor; border-radius: 4px;">RSS / Atom</span>
    <span class="md-tag" style="font-size: 0.9rem; padding: 4px 8px; border: 1px solid currentColor; border-radius: 4px; margin-left: 8px;">LLM Pipelines</span>
    <span class="md-tag" style="font-size: 0.9rem; padding: 4px 8px; border: 1px solid currentColor; border-radius: 4px; margin-left: 8px;">Privacy Optional</span>
  </div>
</div>

Egregora parses your raw data streams (WhatsApp, RSS, etc.), groups content into meaningful stories, and uses composable LLM agents to generate high-quality knowledge feeds.

<div class="grid cards" markdown>

- :material-eye-outline: __[View Demo](https://franklinbaldo.github.io/egregora/demo/)__

    ---

    See a live example of a blog generated from chat data.

- :material-rocket-launch-outline: __[Quick Start](getting-started/quickstart.md)__

    ---

    Install Egregora and generate your first site in minutes.

- :material-creation: __[V3 Architecture](v3/architecture/overview.md)__

    ---

    Explore the next-gen Atom-centric architecture.

- :material-book-open-page-variant-outline: __[User Guide](v2/architecture.md)__

    ---

    Deep dive into the current V2 workflows.

</div>

## Key Features

<div class="grid cards" markdown>

- __Atom Protocol Centric__

    ---

    Built on the open web. Everything is an Entry in a Feed, ensuring interoperability with the entire RSS ecosystem.

- __Composable AI Agents__

    ---

    Assemble pipelines of specialized agents (Writer, Editor, Enricher) to transform raw noise into signal.

- __Privacy Optional__

    ---

    Designed for privacy-first local operation, but flexible enough to leverage powerful cloud LLMs when needed.

- __Feed-to-Feed Transformations__

    ---

    Like Yahoo Pipes for the AI age. Ingest feeds, transform them with LLMs, and publish new feeds.

</div>

## How it works

```bash title="The Egregora Workflow"
# 1. Initialize a new site
egregora init my-knowledge-base

# 2. Process your input (WhatsApp, etc.)
egregora write -f _chat.txt

# 3. Preview your beautiful site
mkdocs serve
```
