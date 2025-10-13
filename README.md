# 🧠 Egregora

> **Egregora is a collective-intelligence compiler—a system that listens to your group chats, extracts their meaning, and rewrites them as if the group itself were speaking.**

It transforms the chaotic, fragmented stream of daily conversation into a coherent, searchable, and permanent archive of your group's shared mind. It’s not just a tool; it’s a philosophy: the universe doesn’t just compute numbers—it computes meaning. Egregora is an attempt to do the same for our digital communities.

---

## ⚡ From Chaos to Clarity

Imagine a typical WhatsApp conversation—a mix of links, ideas, and side-chatter:

> **14:02 — Ana:** vamos postar esse link sobre IA aberta, parece importante: https://example.com/ai-dilemma
> **14:04 — João:** boa! isso toca no ponto que o Pedro levantou ontem sobre os riscos de coordenação.
> **14:05 — Bia:** exato. a abertura total pode ser um "Moloch" tecnológico.
> **14:07 — Ana:** vou adicionar isso nas notas.

Egregora ingests this raw export and produces a clean, anonymized, and enriched narrative:

> ### **Thread 3: The Open AI Dilemma**
>
> We discussed the complexities of open-source AI, prompted by an article on its coordination risks. The conversation highlighted the potential for unintended negative consequences, referencing the concept of a "Moloch" scenario where individual incentives lead to collective failure (*Member-A0B2*, *Member-C4E1*). This connects to our ongoing dialogue about technological ethics.
>
> **Enriched Link:**
> - **[The AI Dilemma](https://example.com/ai-dilemma):** The article argues that while open AI fosters innovation, it also creates coordination problems that could lead to unsafe deployments. Key themes include game theory, systemic risk, and the ethics of public-domain models.

This is the core loop: from fragmented data to collective insight.

---

## 🧩 Architecture: The Mind's Assembly Line

Egregora is built on a modular pipeline that mirrors a cognitive process: from perception to memory.

```mermaid
graph TD
    A[Raw Chat Exports (.zip)] --> B{1. Parse & Structure};
    B --> C[Anonymized Polars DataFrame];
    C --> D{2. Enrich & Analyze};
    D --> E[Content with Context (Links, Media)];
    E --> F{3. Generate Collective Narrative};
    F --> G[Daily Markdown Posts];

    subgraph "🧠 Collective Memory"
        H(Evolving Member Profiles)
        I(RAG Vector Index - ChromaDB)
    end

    E --> H;
    G --> I;

    style B fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#ccf,stroke:#333,stroke-width:2px
    style F fill:#9f9,stroke:#333,stroke-width:2px

```

1.  **Parse & Structure:** WhatsApp exports are parsed into clean, structured Polars DataFrames. Participants are anonymized with deterministic UUIDs to protect privacy while preserving conversational flow.
2.  **Enrich & Analyze:** The system analyzes links and media using Google Gemini, extracting summaries and key themes. This enriched data provides the intellectual context for each day's conversation.
3.  **Generate Collective Narrative:** A powerful prompt engine synthesizes the day's messages into a coherent story, written from the group's perspective ("we discussed," "we explored").
4.  **Update Collective Memory:** The system continuously updates individual member profiles with their intellectual contributions and indexes the final posts in a local RAG (Retrieval-Augmented Generation) vector store, creating a searchable long-term memory.

---

## 🧰 Quickstart

**Goal:** Go from a raw WhatsApp `.zip` export to your first generated post in under 5 minutes.

### Prerequisites

*   **Python 3.11+**
*   **[uv](https://docs.astral.sh/uv/)** for dependency management
*   **Gemini API Key** (free tier available at [Google AI Studio](https://aistudio.google.com/app/apikey))

### Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# 2. Install dependencies
uv sync

# 3. Set your API key
export GEMINI_API_KEY="your-api-key-here"
```

### Run Your First Process

```bash
# 1. Place your WhatsApp export in a known directory
# (e.g., /path/to/your/chat.zip)

# 2. Run the pipeline for the last 3 days
uv run egregora process /path/to/your/chat.zip --days 3

# 3. Check the output
ls -R data/
```

Your first anonymized, enriched, and collectively narrated posts are now in `data/{group-name}/posts/daily/`.

---

## ✨ Core Features

| Feature                 | Description                                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 🧠 **Collective Narration** | Rewrites daily conversations from the group's perspective ("we"), creating a unified, coherent voice.                                  |
| 👥 **Evolving Profiles**    | Automatically tracks the intellectual contributions and patterns of each member, creating dynamic profiles of their thought.           |
| 🔍 **RAG Memory**           | Indexes all generated posts into a local vector store, allowing you to search and query your group's entire conversational history.    |
| 📡 **AI Enrichment**        | Analyzes links and media with Google Gemini, providing summaries and context that become part of the permanent archive.              |
| 💾 **Local-First & Private**  | All processing and data storage happens locally. Your conversations are never sent to a third-party server.                          |
| 🔒 **Deterministic Anonymization** | Protects privacy with consistent, unique identifiers for each participant, preserving conversational flow without revealing identities. |

---

## 📖 Usage Guide

### Basic Commands

```bash
# Process all ZIP files for the last 3 days
uv run egregora process /path/to/zips/*.zip --days 3

# Process a specific date range
uv run egregora process /path/to/zips/*.zip --from-date 2024-01-01 --to-date 2024-01-31

# Preview the processing without writing files
uv run egregora process /path/to/zips/*.zip --dry-run
```

### Profile Management

```bash
# List all generated member profiles
uv run egregora profiles list

# Show the detailed profile for a specific member
uv run egregora profiles show <member-id>
```

---

## 🧬 Extending & Integrating

Egregora is designed to be modular. Key integration points include:

*   **Adding new LLM models:** The `PostGenerator` class in `src/egregora/generator.py` can be adapted to support other models like Llama or Claude.
*   **Custom Enrichment Modules:** The `EnrichmentEngine` in `src/egregora/enrichment.py` can be extended with new analysis tools.
*   **Connecting Chat Sources:** The parsers in `src/egregora/parsers/` can be expanded to support other platforms like Telegram or Signal.
*   **MkDocs Publishing:** The output Markdown is structured for seamless integration with [MkDocs](https://www.mkdocs.org/) to publish your group's archive as a static site.

---

## ⚙️ Development & Contribution

### Setup

```bash
# Install with all development dependencies (tests, linting, docs)
uv sync --all-extras

# Install pre-commit hooks for code quality
uv run pre-commit install
```

### Running Tests

```bash
# Run the full test suite
uv run pytest -q

# Run tests with verbose output
uv run pytest -v

# Run only tests related to a specific feature (e.g., "anonymization")
uv run pytest -k "anonymization"
```

### Contribution Flow

1.  **Fork the repository.**
2.  **Create a feature branch.**
3.  **Make your changes and add tests.**
4.  **Ensure all tests and pre-commit hooks pass.**
5.  **Submit a pull request.**

---

## 📜 License

Egregora is released under the MIT License. See [LICENSE](LICENSE) for details. It relies on the amazing work of projects like [Polars](https://pola.rs/), [LlamaIndex](https://www.llamaindex.ai/), [Diskcache](http://www.grantjenks.com/docs/diskcache/), and [Google Gemini](https://deepmind.google/technologies/gemini/).
