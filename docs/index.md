---
hide:
  - navigation
  - toc
---

# Egregora

<div class="md-hero">
  <p>Turn chaotic chat archives into a structured, readable blog.</p>
</div>

Egregora parses your WhatsApp exports, groups conversations into meaningful stories, and uses LLMs to generate posts that capture the essence of your collective consciousness.

<div class="grid cards" markdown>

- :material-eye-outline: __[View Demo](https://franklinbaldo.github.io/egregora/demo/)__

    ---

    See a live example of a blog generated from chat data.

- :material-rocket-launch-outline: __[Quick Start](getting-started/quickstart.md)__

    ---

    Install Egregora and generate your first site in minutes.

- :material-cogs: __[Configuration](getting-started/configuration.md)__

    ---

    Customize the behavior, LLM models, and output style.

- :material-book-open-page-variant-outline: __[User Guide](guide/architecture.md)__

    ---

    Deep dive into the architecture and workflows.

</div>

## Key Features

<div class="grid cards" markdown>

- __Privacy First__

    ---

    Runs entirely locally. Your chat data never leaves your machine unless you configure an external LLM APIs.

- __AI Powered__

    ---

    Uses advanced LLMs (via LiteLLM) to summarize conversations and extract meaningful narratives.

- __Rich Media__

    ---

    Preserves images and links from your chats, embedding them into the generated posts.

- __Static Site Generation__

    ---

    Outputs standard Markdown compatible with MkDocs, allowing you to host your archive anywhere for free (GitHub Pages, etc).

</div>

## How it works

``` title="Simple Workflow"
# 1. Initialize a new site
egregora init

# 2. Process your chat export
egregora write -f _chat.txt

# 3. Preview your beautiful blog
mkdocs serve
```
