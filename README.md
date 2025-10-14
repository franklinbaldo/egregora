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
    A[Raw Chat Exports (.zip)] --> B{1. Ingest & Anonymize};
    B --> C[Polars DataFrame];
    C --> D{2. Embed with Gemini};
    D --> E[DataFrame with Vectors];
    E --> F{3. Archive to IA};
    F --> G[Parquet on Internet Archive];
    E --> H{4. Local RAG with DuckDB/Ibis};
    H --> I[Context Snippets];
    I --> J{5. Generate Narrative};
    J --> K[Daily Markdown Posts];
    K --> L{6. Build Static Site};
    L --> M[MkDocs Site];

    style B fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#ccf,stroke:#333,stroke-width:2px
    style J fill:#9f9,stroke:#333,stroke-width:2px
    style L fill:#f9c,stroke:#333,stroke-width:2px
```

1.  **Ingest & Anonymize:** WhatsApp exports are parsed into clean, structured Polars DataFrames. Participants are anonymized with deterministic UUIDs.
2.  **Embed with Gemini:** The text content is converted into vector embeddings using Google's Gemini models.
3.  **Archive to Internet Archive:** The DataFrame with embeddings is exported to a Parquet file and uploaded to the Internet Archive for long-term, zero-cost storage.
4.  **Local RAG with DuckDB/Ibis:** An ephemeral RAG server is started, loading the embeddings into an in-memory DuckDB database with a VSS index for fast similarity search via Ibis.
5.  **Generate Narrative:** A powerful Jinja2 prompt engine synthesizes the day's messages, enriched with context from the RAG server, into a coherent story.
6.  **Build Static Site:** The generated Markdown posts are used to build a static website with MkDocs, ready for local preview or deployment.

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

# 2. Run the full pipeline
uv run egregora pipeline /path/to/your/chat.zip

# 3. Check the output
ls -R posts/
```

Your first anonymized, enriched, and collectively narrated posts are now in `posts/`.

---

## ✨ Core Features

| Feature                 | Description                                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 🧠 **Collective Narration** | Rewrites daily conversations from the group's perspective ("we"), creating a unified, coherent voice.                                  |
| 🔍 **Local RAG Memory**     | Indexes all generated posts into a local, in-memory vector store, allowing you to search and query your group's entire conversational history. |
| 📡 **AI Enrichment**        | Analyzes links and media with Google Gemini, providing summaries and context that become part of the permanent archive.              |
| 💾 **Local-First & Private**  | All processing and data storage happens locally. Your conversations are never sent to a third-party server.                          |
| 🔒 **Deterministic Anonymization** | Protects privacy with consistent, unique identifiers for each participant, preserving conversational flow without revealing identities. |
| 📦 **Zero-Cost Archival**   | Exports embeddings to Parquet files and archives them on the Internet Archive for free, long-term storage.                           |

---

## 📖 Usage Guide

### Basic Commands

```bash
# Run the full pipeline
uv run egregora pipeline /path/to/your/chat.zip

# Ingest a ZIP file and save the DataFrame
uv run egregora ingest run /path/to/your/chat.zip --output ingest.parquet

# Generate embeddings from a DataFrame
uv run egregora embed run ingest.parquet --output embeddings.parquet

# Start the RAG server
uv run egregora rag serve embeddings.parquet

# Generate posts with RAG context
uv run egregora gen run /path/to/your/chat.zip --inject-rag

# Build the static site
uv run egregora gen run /path/to/your/chat.zip --preview

# Archive the embeddings
uv run egregora archive upload embeddings.parquet
```

---

## 🧬 Extending & Integrating

Egregora is designed to be modular. Key integration points include:

*   **Adding new LLM models:** The `PostGenerator` class in `src/egregora/generate/core.py` can be adapted to support other models like Llama or Claude.
*   **Custom Enrichment Modules:** The `ContentEnricher` in `src/egregora/enrichment.py` can be extended with new analysis tools.
*   **Connecting Chat Sources:** The parser in `src/egregora/parser.py` can be expanded to support other platforms like Telegram or Signal.
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
