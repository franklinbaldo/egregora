---
title: About Egregora
description: How the group's collective consciousness works
---

# About Egregora

## What is Egregora?

Egregora is a system that transforms WhatsApp conversations into analytical blog posts. Using artificial intelligence (LLM), it:

1. **Analyzes** group conversations
2. **Identifies** topics and emerging narratives
3. **Synthesizes** discussions into structured posts
4. **Preserves** the complexity and divergences of collective thought

## How does it work?

### Ultra-Simple Pipeline

```
WhatsApp ZIP → Parse → Anonymize → Group → Enrich → LLM → Posts
```

### Privacy First

- **Automatic anonymization**: All names converted to UUID5 pseudonyms
- **Deterministic**: Same person always gets the same UUID
- **Full opt-out**: Any participant can leave with `/egregora opt-out`
- **Optional aliases**: `/egregora set alias "Name"` for humanized identity

See [ALIASES.md](https://github.com/franklinbaldo/egregora/blob/main/ALIASES.md) for details.

### LLM Editorial Control

The LLM (Gemini) has complete control over:

- ✅ **What's worth writing** (filters noise automatically)
- ✅ **How many posts** (0-N per period)
- ✅ **All metadata** (title, slug, tags, summary)
- ✅ **Content quality** (editorial judgment)

## Technology

- **Parsing**: Python + Ibis on DuckDB (DataFrames)
- **LLM**: Google Gemini (multi-turn tool calling)
- **RAG**: DuckDB VSS + Parquet (3072-dim embeddings)
- **Site**: MkDocs Material
- **Privacy**: UUID5 + opt-out + filtering

## Open Source

This project is open source: [github.com/franklinbaldo/egregora](https://github.com/franklinbaldo/egregora)

---

*Egregora v2 - Ultra-simple WhatsApp → Blog pipeline*