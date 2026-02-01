---
hide:
  - navigation
  - toc
---

# Egregora

<div class="md-hero" style="text-align: center; padding: 2rem 0;">
  <h1>Egregora</h1>
  <p style="font-size: 1.5rem; font-weight: 300;">Turn your conversations into stories that remember<br>AI-Powered Narrative Generation with Contextual Memory</p>
  <div style="margin-top: 1rem;">
    <span class="md-tag" style="font-size: 0.9rem; padding: 4px 8px; border: 1px solid currentColor; border-radius: 4px;">Contextual Memory</span>
    <span class="md-tag" style="font-size: 0.9rem; padding: 4px 8px; border: 1px solid currentColor; border-radius: 4px; margin-left: 8px;">Content Discovery</span>
    <span class="md-tag" style="font-size: 0.9rem; padding: 4px 8px; border: 1px solid currentColor; border-radius: 4px; margin-left: 8px;">Privacy First</span>
  </div>
</div>

Egregora transforms your chat history into beautiful, connected narratives. Unlike simple chat-to-text tools, it uses AI to understand context, discover your best memories, and create loving portraits of the people in your conversations. All three magical features work automatically with zero configuration.

<div class="grid cards" markdown>

- :material-eye-outline: __[View Demo](https://franklinbaldo.github.io/egregora/demo/)__

    ---

    See a live example of a blog generated from chat data.

- :material-rocket-launch-outline: __[Quick Start](./getting-started/quickstart.md)__

    ---

    Install Egregora and generate your first site in minutes.

- :material-creation: __[Architecture](v3/architecture/overview.md)__

    ---

    Explore the Atom-centric architecture.

</div>

## What Makes Egregora Magical

<div class="grid cards" markdown>

- __🧠 Contextual Memory (RAG)__

    ---

    Posts aren't isolated summaries—they reference previous discussions, creating connected narratives that feel like a continuing story.

- __🏆 Content Discovery__

    ---

    Automatically identifies and ranks your most meaningful conversations, surfacing the best memories in a "Top Posts" section.

- __💝 Author Profiles__

    ---

    Creates emotional portraits of each person from their messages—storytelling that captures personality, not statistical analysis.

- __🔒 Privacy First__

    ---

    Runs entirely on your local machine by default. Your conversations never leave your computer unless you choose to publish.

</div>

## Additional Features

<div class="grid cards" markdown>

- __Rich Media__

    ---

    Images and videos are automatically extracted, optimized, and embedded with AI-generated descriptions.

- __Beautiful Design__

    ---

    AI-generated cover images and Material for MkDocs templates create a polished, professional blog.

- __Highly Customizable__

    ---

    Power users can customize models, prompts, and pipelines—but sensible defaults work for 95% of users.

- __Open & Interoperable__

    ---

    Built on Atom/RSS standards. Everything is a feed entry, ensuring ecosystem compatibility.

</div>

## How it works

```bash title="The Egregora Workflow"
# 1. Initialize a new site
egregora init my-knowledge-base

# 2. Process your input (WhatsApp, etc.)
egregora write -f _chat.txt

# 3. Preview your beautiful site
uv tool run --from "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs serve -f .egregora/mkdocs.yml
```
