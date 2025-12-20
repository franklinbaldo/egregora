# Custom Prompt Overrides

This directory lets you override the default prompts that ship with Egregora. The loader resolves
overrides in this order:

1. `.egregora/prompts/*.jinja` (your local customizations)
2. `src/egregora/prompts/*.jinja` (package defaults)

Place a file here with the **same filename** as the package version and it will be used automatically.

## Available Prompts

| File | Purpose |
| --- | --- |
| `writer.jinja` | Main writer-agent prompt that converts conversation windows into posts |
| `media_detailed.jinja` | Rich media enrichment template (images, video, audio, docs) |
| `url_detailed.jinja` | URL enrichment template used for linked articles |

> The prompt directory is intentionally flat—no `system/` or `enrichment/` subfolders. This keeps overrides easy
> to reason about and avoids stale nested copies.

## Example: Customize the Writer Prompt

```bash
# 1. Ensure the prompts directory exists
mkdir -p .egregora/prompts

# 2. Copy the package default
cp src/egregora/prompts/writer.jinja .egregora/prompts/writer.jinja

# 3. Edit your version
$EDITOR .egregora/prompts/writer.jinja

# 4. Run Egregora – it will automatically pick up the override
egregora write export.zip --output blog
```

## Directory Structure

```
.egregora/
└── prompts/
    ├── README.md        # This file
    ├── writer.jinja     # Optional override for the writer agent
    ├── media_detailed.jinja
    └── url_detailed.jinja
```

## Tips

- Start with small edits and run `egregora write` against a trimmed dataset to validate the behavior.
- Commit your custom prompts so you can track prompt experiments alongside code.
- Delete a custom `.jinja` file to revert to the built-in default.

Prompts are standard [Jinja2](https://jinja.palletsprojects.com/templates/) templates, so you can use loops,
conditionals, includes, and macros as needed.
