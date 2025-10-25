Egregora 🤖 → 📝

Emergent Group Reflection Engine Generating Organized Relevant Articles

Transform your WhatsApp group chats into intelligent, privacy-first blogs where collective conversations emerge as beautifully written articles.

https://img.shields.io/badge/python-3.11+-blue.svg
https://img.shields.io/badge/License-MIT-yellow.svg
https://img.shields.io/badge/uv-powered-FF6C37.svg

✨ Why Egregora?

Egregora lives up to its name as an Emergent Group Reflection Engine:

· 🧠 Emergent Intelligence - Collective conversations synthesize into coherent articles
· 👥 Group Reflection - Your community's unique voice and insights are preserved
· ⚙️ Engine - AI-powered pipeline that works automatically
· 📊 Organized - Smart clustering into relevant topics and threads
· 🎯 Relevant - Filters noise, focuses on substantive discussions
· 📝 Articles - Professional-quality blog posts ready to publish

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

extra:
  egregora:
    group_slug: ai-safety-group
    timezone: America/New_York
    custom_instructions: |
      Focus on technical depth and concrete examples.
      Adopt Scott Alexander's writing style.
```

🏗️ How the "Reflection Engine" Works

```
Group Conversations
    → Parse & Anonymize
    → AI Editorial Judgment ← Emergent Intelligence
    → Multi-post Generation ← Organized & Relevant
    → Beautiful Static Site ← Professional Articles
```

The Magic of Emergence

Instead of rigid rules, Egregora trusts the AI to:

· Detect emergent themes from raw conversations
· Reflect group dynamics and collective thinking
· Engineer coherent narratives from fragmented discussions
· Generate organized content with proper structure
· Surface relevant insights while filtering noise
· Produce article-quality writing automatically

📚 Example Output

From messy group chat:

```
User1: did u see that AI paper?
User2: yeah the mesa-optimizer part got me thinking
User1: https://example.com/paper
User3: reminds me of our convo last week about inner alignment
```

To organized, relevant article:

```markdown
---
title: "Why Mesa-Optimizers Keep Me Up at Night"
slug: mesa-optimizers-concern
date: 2025-01-15
tags: [AI safety, optimization, alignment]
---

I've been thinking about mesa-optimizers again after reading the latest paper on...

## The Inner Alignment Problem Revisited

This connects back to our previous discussion about...
```

📊 Cost Estimation

Processing uses Google Gemini API. Approximate costs:

Group Activity Messages/Day Cost/Day Cost/Month
Small group 10-50 $0.01-0.05 $0.30-1.50
Active group 100-500 $0.10-0.50 $3-15
Very active 1000+ $1-5 $30-150

Cost-saving tips: Use --from-date and --to-date to process small ranges, disable enrichment with --enable-enrichment=False.

🛠️ Development

For Contributors

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with development dependencies
uv sync

# Run tests
uv run pytest tests/
uv run ruff check src/
```

Architecture Highlights

· Privacy-first: Anonymization happens before AI sees any data
· DataFrames all the way: Built on Polars for performance
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

Ready to see emergence in action?

```bash
# Install uv then run everything with zero installation
uvx --from git+https://github.com/franklinbaldo/egregora egregora init my-blog
```

Egregora: From the Greek concept of a collective group mind or emergent consciousness.