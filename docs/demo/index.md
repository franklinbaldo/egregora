# Demo Blog

Explore a sample Egregora site powered by the actual CLI pipeline. The posts
below come from running:

```bash
uv run egregora init docs/demo --no-interactive
uv run python dev_tools/generate_demo.py
```

Make sure `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) is set so `egregora write` can
call Gemini while generating the blog.

{{ blog_content }}
