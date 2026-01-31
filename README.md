# Egregora

*Turn your conversations into stories that remember.*

[![CI](https://github.com/franklinbaldo/egregora/actions/workflows/ci.yml/badge.svg)](https://github.com/franklinbaldo/egregora/actions/workflows/ci.yml)
[![CodeQL](https://github.com/franklinbaldo/egregora/actions/workflows/codeql.yml/badge.svg)](https://github.com/franklinbaldo/egregora/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/franklinbaldo/egregora/branch/main/graph/badge.svg)](https://codecov.io/gh/franklinbaldo/egregora)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Pydantic-AI](https://img.shields.io/badge/Pydantic--AI-type--safe-00D9FF.svg)](https://ai.pydantic.dev/)
[![Docs](https://img.shields.io/badge/docs-live-green.svg)](https://franklinbaldo.github.io/egregora/)

**Egregora** transforms your chat history into a beautiful blog that tells the story of your conversations. Unlike simple chat-to-text tools, Egregora uses AI to understand context, discover your best memories, and create loving portraits of the people in your chats. It runs locally by default, keeping your data private while using modern LLMs (like Gemini or OpenRouter) to create something magical.

## ✨ What Makes Egregora Special

Egregora doesn't just convert chats to text—it understands your conversations and creates connected narratives. Three features work automatically to make this magic happen:

### 🧠 **Contextual Memory** - Posts That Remember
Your blog posts aren't isolated summaries. They reference previous discussions, building on earlier points and creating a continuing narrative. The AI "remembers" what was said before, so reading your blog feels like reliving the natural flow of your conversations.

### 🏆 **Content Discovery** - Find Your Treasures
Egregora automatically identifies your most meaningful conversations and surfaces them in a "Top Posts" section. No more scrolling through hundreds of posts to find the gems—your best memories are always easy to find and share.

### 💝 **Author Profiles** - Loving Portraits
The AI creates beautiful profiles of each person in your chats, capturing their personality, quirks, and unique voice. These aren't statistical reports—they're emotional storytelling that makes you think "This IS them!"

**All three features work automatically with zero configuration.** That's the magic.

---

## 🚀 Getting Started

Egregora transforms a WhatsApp export (ZIP) into a static website powered by [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

### 1. Installation

Install Egregora using [uv](https://github.com/astral-sh/uv) (requires Python 3.12+):

> **Tip:** Don't worry if this command looks complicated! It just installs the tool and everything it needs. Simply copy and paste it into your terminal.

```bash
uv tool install git+https://github.com/franklinbaldo/egregora
```

You will also need a Google Gemini API key (free tier available):

```bash
export GOOGLE_API_KEY="your-api-key"
```

### 2. The Workflow

It's this simple:

**1. Initialize a new site:**

```bash
egregora init ./my-blog
cd my-blog
```

**2. Generate posts from your chat export:**

```bash
egregora write whatsapp-export.zip --output-dir=. --timezone='America/New_York'
```

That's it! Egregora will automatically:
- ✨ Create posts that reference previous discussions (Contextual Memory)
- 🏆 Identify and rank your best memories (Content Discovery)
- 💝 Generate profiles of each person in the chat (Author Profiles)
- 🖼️ Extract and optimize images/videos
- 🎨 Create cover images for posts

**3. Preview your site:**

Use `uv tool run` to start a local server without installing the packages globally.

```bash
uv tool run --from "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs serve -f .egregora/mkdocs.yml
```

*Visit <http://localhost:8000> to experience the magic.*

---

## 🛠️ Configuration

Egregora is highly configurable via the `.egregora.toml` file generated in your site directory.

* **Models:** Switch between models (e.g., `google-gla:gemini-flash-latest`) or use OpenRouter.
* **Pipeline:** Adjust how many days of chat form a single post (`step_size`, `step_unit`).

👉 **[Full Configuration Reference](docs/getting-started/configuration.md)**

### Customizing the AI

* **Prompts:** Edit `.egregora/prompts/writer.jinja` to change the tone and style of the writing.
* **Instructions:** Add custom instructions in `.egregora.toml` under `[writer]` `custom_instructions`.

---

## 🎯 More Features

Beyond the three magical features above, Egregora includes:

### 🖼️ **Rich Media Handling**
Images and videos are automatically extracted from your chat exports, optimized for the web, and embedded in posts. Media descriptions are generated for accessibility and context.

### 🎨 **Beautiful Cover Images**
Each post gets a unique AI-generated cover image based on its content, giving your blog a polished, professional look.

### 🔒 **Privacy Controls**
Anonymize author names, strip EXIF data from images, and control exactly what information appears in your blog. Privacy is built in, not bolted on.

### 📱 **Works Offline**
Generate your blog entirely on your local machine. Your conversations never leave your computer unless you choose to publish them.

### 🌍 **Multilingual**
Write posts in any language—Spanish, French, Portuguese, or any language your AI model supports.

### ⚙️ **Highly Customizable**
Power users can customize everything: AI models, prompts, windowing parameters, enrichment settings, and more. But you don't need to touch any of this—sensible defaults work for 95% of users.

---

## 👩‍💻 Developer Guide

Egregora is built with a focus on performance and maintainability.

### Project Structure

* `src/egregora/orchestration/`: High-level workflows that coordinate the pipeline.
* `src/egregora/agents/`: AI logic powered by **Pydantic-AI**.
* `src/egregora/database/`: Data persistence using **DuckDB** and **LanceDB**.
* `src/egregora/input_adapters/`: Logic for reading different data sources.

### Performance (Internals)

We use **Ibis** and **DuckDB** to handle large datasets efficiently.

* **Streaming:** Large ZIP files are processed without loading everything into RAM.
* **Functional Transforms:** Data flows through pure functions (`Table -> Table`) for speed and reliability.

### Adding New Adapters

You can extend Egregora to read from other sources (e.g., Slack, Telegram) by implementing the `InputAdapter` protocol in `src/egregora/input_adapters/base.py`.

---

## 🤝 Contributing

We welcome contributions! Please check out:

* **[Technical Reference](docs/reference/):** Deep dive into CLI commands and architecture.
* **[Code of the Weaver](CLAUDE.md):** Guidelines for contributors and AI agents.

To run tests:

```bash
uv sync --all-extras
uv run pytest tests/
```

## ⚠️ Legacy Notes

<details>
<summary>Legacy Upgrade Notes (Internal/Mailbox)</summary>

The mailbox storage backend has been updated from **Maildir** to **MH**.
**Before running the new version:**
1. Delete any existing mailbox directories (e.g., `.team/personas/*/mail` or `.team/mail`).
2. The new system will create a shared mailbox at `.team/mail` using the MH format.
3. Old messages are **not** migrated automatically.
</details>
