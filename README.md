# Egregora v3 🤖 → 📝

**Emergent Group Reflection Engine Generating Organized Relevant Articles**

Transform your WhatsApp group chats into intelligent, privacy-first blogs where collective conversations emerge as beautifully written articles.

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Powered by uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)

✨ **Why Egregora v3?**

Egregora v3 is a greenfield rewrite focusing on a stateless, single-stack architecture using Ibis, DuckDB, and VSS.

- **🧠 Emergent Intelligence**: Collective conversations synthesize into coherent articles.
- **👥 Group Reflection**: Your community's unique voice and insights are preserved.
- **⚙️ Engine**: A stateless, AI-powered pipeline that works automatically.
- **🛡️ Deterministic Privacy**: Your anonymization logic, preserved and guaranteed.

---

🚀 **Quick Start**

1.  **Install `uv`** (if you haven't already):
    ```bash
    # On macOS/Linux:
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # On Windows (PowerShell):
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

2.  **Run Egregora v3 (zero installation required!)**
    ```bash
    # Initialize your project (creates egregora.db and config)
    uvx --from git+https://github.com/franklinbaldo/egregora egregora eg3 init

    # Provide your Gemini API key
    export GOOGLE_API_KEY="your-google-gemini-api-key"

    # Ingest your data
    uvx --from git+https://github.com/franklinbaldo/egregora egregora eg3 ingest --src /path/to/your/data

    # Build the vector index
    uvx --from git+https://github.com/franklinbaldo/egregora egregora eg3 build

    # Query your data
    uvx --from git+https://github.com/franklinbaldo/egregora egregora eg3 query --q "What are we talking about?"
    ```

---

🏗️ **Architecture**

Egregora v3 is built on a clean, layered architecture:

- **Core**: Configuration, context, database management, and paths.
- **Adapters**: Pluggable components for embeddings, vector stores, and I/O.
- **Features**: RAG, ranking, and site generation logic.
- **CLI**: A thin Typer-based command-line interface.

The data model is a single DuckDB file containing `rag_chunks`, `rag_vectors`, and ranking tables.

---

🛠️ **Development**

For Contributors:

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with development dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/v3/
uv run ruff check src/egregora_v3/
```

---

📄 **License**

MIT License - see the `LICENSE` file for details.
