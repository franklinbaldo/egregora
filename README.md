# Egregora
> *Turn your chaotic group chat into a structured, readable blog.*

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)
[![Pydantic-AI](https://img.shields.io/badge/Pydantic--AI-type--safe-00D9FF.svg)](https://ai.pydantic.dev/)

**Egregora** is a tool that reads your chat history and writes a blog. It uses AI to filter noise, synthesize conversations, and generate engaging posts. It is designed to run locally, keeping your data private by default, while using modern LLMs (like Gemini or OpenRouter) to do the heavy lifting of writing and formatting.

---

## 🚀 Getting Started

Egregora transforms a WhatsApp export (ZIP) into a static website powered by [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

### 1. Prerequisites
You need **Python 3.12+** and **[uv](https://github.com/astral-sh/uv)** installed. You will also need a Google Gemini API key (free tier available).

```bash
export GOOGLE_API_KEY="your-api-key"
```

### 2. The Workflow

**1. Initialize a new site:**
```bash
uvx --from git+https://github.com/franklinbaldo/egregora \
    egregora init ./my-blog
cd my-blog
```

**2. Generate posts from your chat export:**
```bash
uv run egregora write path/to/chat_export.zip --output=.
```

**3. Preview your site:**
```bash
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```
*Visit http://localhost:8000 to read your new blog.*

---

## 🛠️ Configuration

Egregora is highly configurable via the `.egregora/config.yml` file generated in your site directory.

*   **Models:** Switch between models (e.g., `google-gla:gemini-2.0-flash`, `google-gla:gemini-1.5-pro`) or use OpenRouter.
*   **Privacy:** Configure PII redaction and anonymization.
*   **Pipeline:** Adjust how many days of chat form a single post (`step_size`, `step_unit`).

👉 **[Full Configuration Reference](docs/configuration.md)**

### Customizing the AI
*   **Prompts:** Edit `.egregora/prompts/writer.jinja` to change the tone and style of the writing.
*   **Instructions:** Add custom instructions in `config.yml` under `writer.custom_instructions`.

---

## ✨ Features

### 🧠 Context & Memory (RAG)
Egregora uses **LanceDB** to build a vector knowledge base of your conversations. When writing a new post, the AI "remembers" related discussions from the past, adding depth and continuity to the narrative.

### 🖼️ Rich Media
Images and videos shared in the chat are automatically extracted, optimized, and embedded in the posts. An "Enricher" agent analyzes images to provide descriptions for the Writer agent.

### 🎨 Visuals
A dedicated **Banner Agent** generates unique cover images for each post based on its content, giving your blog a polished look.

### 📊 Ranking & Quality
The **Reader Agent** uses an ELO rating system to evaluate and rank posts, helping you surface the best content from your archives.

---

## 👩‍💻 Developer Guide

Egregora is built with a focus on performance and maintainability.

### Project Structure
*   `src/egregora/orchestration/`: High-level workflows that coordinate the pipeline.
*   `src/egregora/agents/`: AI logic powered by **Pydantic-AI**.
*   `src/egregora/database/`: Data persistence using **DuckDB** and **LanceDB**.
*   `src/egregora/input_adapters/`: Logic for reading different data sources.

### Performance (Internals)
We use **Ibis** and **DuckDB** to handle large datasets efficiently.
*   **Streaming:** Large ZIP files are processed without loading everything into RAM.
*   **Functional Transforms:** Data flows through pure functions (`Table -> Table`) for speed and reliability.

### Adding New Adapters
You can extend Egregora to read from other sources (e.g., Slack, Telegram) by implementing the `InputAdapter` protocol in `src/egregora/input_adapters/base.py`.

---

## 🤝 Contributing

We welcome contributions! Please check out:

*   **[Technical Reference](docs/reference.md):** Deep dive into CLI commands and architecture.
*   **[Code of the Weaver](CLAUDE.md):** Guidelines for contributors and AI agents.

To run tests:
```bash
uv sync --all-extras
uv run pytest tests/
```
