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

🛡️ Privacy by Design

· Automatic anonymization - Real names never reach the AI
· User-controlled data - /egregora opt-out to exclude your messages
· Deterministic UUIDs - Same person gets same pseudonym every time

🚀 Quick Start

1. Install uvx

```bash
# On macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip (if you have Python):
pip install uv
```

2. Create and serve your blog (zero installation required!)

```bash
# Initialize your blog site
uvx --from git+https://github.com/franklinbaldo/egregora egregora init my-blog
cd my-blog

# Provide your Gemini API key (required)
export GOOGLE_API_KEY="your-google-gemini-api-key"
#   • On Windows (PowerShell): $Env:GOOGLE_API_KEY = "your-google-gemini-api-key"
#   • Alternatively, pass --gemini-key "your-google-gemini-api-key" to the command below

# Process your WhatsApp export
uvx --from git+https://github.com/franklinbaldo/egregora egregora process \
  whatsapp-export.zip --output=. --timezone='America/New_York'

# Serve your blog (no pip install needed!)
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

Open http://localhost:8000 to see your AI-generated blog!

🧩 Runtime Requirements

Egregora ships with DuckDB in its default installation. The RAG retriever relies on the
[DuckDB VSS extension](https://duckdb.org/docs/extensions/vss.html) to power approximate
nearest-neighbor search. The first `egregora process` run will attempt to download and load
this extension automatically. Make sure the machine running the pipeline can reach the DuckDB
extension repository or preinstall it manually:

```bash
duckdb -c "INSTALL vss; LOAD vss"
```

If you are running in an offline or firewalled environment, fall back to exact retrieval with
`--retrieval-mode exact` until the extension is available. The pytest suite also expects DuckDB
to be installed; run `uv sync` or `pip install duckdb` before executing `pytest` to avoid the
guarded skip in `tests/conftest.py`.

🎪 Advanced Features

Rank Your Posts

```bash
# Run ELO comparisons to find your best content
uvx --from git+https://github.com/franklinbaldo/egregora egregora rank --site-dir=. --comparisons=50
```

AI-Powered Editing

```bash
# Let the AI improve an existing post
uvx --from git+https://github.com/franklinbaldo/egregora egregora edit posts/2025-01-15-ai-safety.md
```

User Privacy Controls

In your WhatsApp group, users can control their data:

```
/egregora set alias "Casey"      # Set display name
/egregora set bio "AI researcher" # Add profile bio
/egregora opt-out                # Exclude from future posts
/egregora opt-in                 # Include in future posts
```

⚙️ Configuration

Customize your blog via mkdocs.yml:

```yaml
site_name: Our AI Safety Discussions
site_url: https://our-group.blog

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

Architecture Highlights

· Privacy-first: Anonymization happens before AI sees any data
· DataFrames all the way: Powered by Ibis + DuckDB for performance
· Functional pipeline: Simple, composable functions over complex agents
· DuckDB storage: Fast vector operations for RAG and rankings

🤝 Community & Support

· Documentation: docs/ - Comprehensive guides and API reference
· Issues: GitHub Issues - Bug reports and feature requests
· Discussions: GitHub Discussions - Questions and community support

📄 License

MIT License - see LICENSE file for details.

🙏 Acknowledgments

Egregora follows the philosophy of "trusting the LLM" - instead of micromanaging with complex heuristics, we give the AI the data and let it make editorial decisions. This results in simpler code and often better outcomes.

Built with the amazing uv Python package manager.

---

📄 **License**

MIT License - see the `LICENSE` file for details.
