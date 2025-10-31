# Independent Pipeline Stage CLI Design

## Overview
This design enables each pipeline stage to be run independently via CLI with explicit artifact saving/loading.

## Pipeline Stages

### 1. Parse Stage
**Purpose:** Convert WhatsApp ZIP export to structured CSV

**Command:**
```bash
egregora parse <zip_file> \
  --output <output.csv> \
  [--timezone TIMEZONE]
```

**Input:** WhatsApp ZIP file
**Output:** CSV file with columns: timestamp, date, time, author (anonymized), message, group_slug, group_name, original_line, tagged_line

**Example:**
```bash
egregora parse chat.zip --output messages.csv --timezone America/New_York
```

### 2. Group Stage
**Purpose:** Split messages into periods (day/week/month)

**Command:**
```bash
egregora group <input.csv> \
  --period {day|week|month} \
  --output-dir <output_dir> \
  [--from-date YYYY-MM-DD] \
  [--to-date YYYY-MM-DD]
```

**Input:** CSV file from parse stage
**Output:** Multiple CSV files in output_dir, named `{period_key}.csv` (e.g., `2025-01-15.csv`, `2025-W03.csv`)

**Example:**
```bash
egregora group messages.csv --period week --output-dir ./periods/
```

### 3. Enrich Stage
**Purpose:** Add LLM-generated context for URLs and media

**Command:**
```bash
egregora enrich <input.csv> \
  --zip-file <original_zip> \
  --output <enriched.csv> \
  --site-dir <site_directory> \
  [--gemini-key API_KEY] \
  [--enable-url / --no-enable-url] \
  [--enable-media / --no-enable-media] \
  [--max-enrichments N]
```

**Input:**
- CSV file (period-specific or full messages)
- Original ZIP file (for media extraction)

**Output:** Enriched CSV with added context rows

**Example:**
```bash
egregora enrich periods/2025-W03.csv \
  --zip-file chat.zip \
  --output enriched/2025-W03-enriched.csv \
  --site-dir ./my-blog \
  --gemini-key $GOOGLE_API_KEY
```

### 4. Gather Context Stage
**Purpose:** Collect all context needed for post generation (RAG, profiles, freeform memory)

**Command:**
```bash
egregora gather-context <input.csv> \
  --period-key <period_identifier> \
  --site-dir <site_directory> \
  --output <context.json> \
  [--gemini-key API_KEY] \
  [--enable-rag / --no-enable-rag] \
  [--retrieval-mode {ann|exact}] \
  [--retrieval-nprobe N] \
  [--retrieval-overfetch N]
```

**Input:** Enriched CSV file
**Output:** JSON file containing:
- Conversation markdown (formatted message table)
- RAG-retrieved similar posts (if enabled)
- Media search results (if RAG enabled)
- Author profiles
- Freeform memory from previous period
- Site configuration (markdown extensions, custom prompts)

**Example:**
```bash
egregora gather-context enriched/2025-W03-enriched.csv \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --output context/2025-W03-context.json \
  --gemini-key $GOOGLE_API_KEY
```

**Benefits:**
- Inspect exactly what context the LLM will receive
- Debug RAG retrieval separately from generation
- Re-run post generation without re-querying RAG
- Share context for reproducibility

### 5. Write Posts Stage
**Purpose:** Generate blog posts from enriched messages + context

**Command:**
```bash
egregora write-posts <input.csv> \
  --context <context.json> \
  --period-key <period_identifier> \
  --site-dir <site_directory> \
  [--gemini-key API_KEY] \
  [--model MODEL_NAME]
```

**Input:**
- Enriched CSV file
- Context JSON file (from gather-context stage)

**Output:** Blog posts in `site-dir/docs/posts/` and profiles in `site-dir/docs/profiles/`

**Example:**
```bash
egregora write-posts enriched/2025-W03-enriched.csv \
  --context context/2025-W03-context.json \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --gemini-key $GOOGLE_API_KEY
```

**Alternative (inline context):**
If `--context` is not provided, the command will gather context inline (backward compatibility)

## Data Format: CSV Schema

All CSV files follow the MESSAGE_SCHEMA structure:

```csv
timestamp,date,time,author,message,original_line,tagged_line,group_slug,group_name
2025-01-15T14:30:00,2025-01-15,14:30,a3f8c2b1,"Hello world",...
```

**Columns:**
- `timestamp`: ISO 8601 timestamp with timezone
- `date`: Date portion (YYYY-MM-DD)
- `time`: Time portion (HH:MM)
- `author`: Anonymized UUID (8 characters)
- `message`: Message text with media placeholders
- `original_line`: Raw WhatsApp export line
- `tagged_line`: Processed line with tags (can be null)
- `group_slug`: Group identifier (kebab-case)
- `group_name`: Human-readable group name

## Implementation Notes

### Serialization Helper
Create `src/egregora/orchestration/serialization.py`:
- `save_table_to_csv(table: Table, output_path: Path)`
- `load_table_from_csv(input_path: Path) -> Table`

### DuckDB Backend Management
Each CLI command should:
1. Initialize DuckDB backend
2. Set as default Ibis backend
3. Perform operations
4. Clean up connection

### State Management
- **Parse stage:** No external state required
- **Group stage:** No external state required
- **Enrich stage:**
  - Requires media extraction from ZIP
  - Uses enrichment cache (`.egregora-cache/`)
  - Saves media to `site-dir/docs/media/`
- **Gather context stage:**
  - Reads RAG database from `site-dir/docs/rag/` (if RAG enabled)
  - Reads profiles from `site-dir/docs/profiles/`
  - Reads freeform memory from `site-dir/docs/posts/freeform/`
  - Reads site config from `site-dir/mkdocs.yml`
  - No state mutations
- **Write posts stage:**
  - Writes posts to `site-dir/docs/posts/`
  - Updates profiles in `site-dir/docs/profiles/`
  - May write freeform content to `site-dir/docs/posts/freeform/`
  - Uses checkpoint store (optional)

## Workflow Examples

### Example 1: Full manual pipeline
```bash
# 1. Parse
egregora parse chat.zip --output messages.csv

# 2. Group by week
egregora group messages.csv --period week --output-dir ./periods/

# 3. Enrich each period
for period in periods/*.csv; do
  egregora enrich "$period" \
    --zip-file chat.zip \
    --output "enriched/$(basename $period)" \
    --site-dir ./my-blog
done

# 4. Gather context for each period
for enriched in enriched/*.csv; do
  period_key=$(basename "$enriched" .csv | sed 's/-enriched//')
  egregora gather-context "$enriched" \
    --period-key "$period_key" \
    --site-dir ./my-blog \
    --output "context/${period_key}-context.json"
done

# 5. Write posts for each period
for enriched in enriched/*.csv; do
  period_key=$(basename "$enriched" .csv | sed 's/-enriched//')
  egregora write-posts "$enriched" \
    --context "context/${period_key}-context.json" \
    --period-key "$period_key" \
    --site-dir ./my-blog
done
```

### Example 2: Re-run enrichment only
```bash
# Re-enrich a specific period with different settings
egregora enrich periods/2025-W03.csv \
  --zip-file chat.zip \
  --output enriched/2025-W03-enriched-v2.csv \
  --site-dir ./my-blog \
  --no-enable-url \
  --enable-media
```

### Example 3: Re-generate posts with different model (without re-gathering context)
```bash
# Gather context once
egregora gather-context enriched/2025-W03-enriched.csv \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --output context/2025-W03-context.json

# Try different models without re-querying RAG
egregora write-posts enriched/2025-W03-enriched.csv \
  --context context/2025-W03-context.json \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --model gemini-2.0-flash-exp

# Not happy? Try a different model with same context
egregora write-posts enriched/2025-W03-enriched.csv \
  --context context/2025-W03-context.json \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --model gemini-1.5-pro-002
```

### Example 4: Debug RAG retrieval
```bash
# Gather context and inspect what RAG returned
egregora gather-context enriched/2025-W03-enriched.csv \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --output context/2025-W03-context.json \
  --enable-rag \
  --retrieval-mode ann

# Inspect the context file
jq '.rag_similar_posts' context/2025-W03-context.json

# Try different retrieval settings
egregora gather-context enriched/2025-W03-enriched.csv \
  --period-key 2025-W03 \
  --site-dir ./my-blog \
  --output context/2025-W03-context-exact.json \
  --enable-rag \
  --retrieval-mode exact

# Compare results
diff <(jq '.rag_similar_posts' context/2025-W03-context.json) \
     <(jq '.rag_similar_posts' context/2025-W03-context-exact.json)
```

## Benefits

1. **Debugging:** Inspect CSV artifacts at each stage
2. **Iteration:** Re-run specific stages without starting over
3. **Cost Control:** Skip enrichment for testing post generation
4. **Experimentation:** Try different models/parameters on same data
5. **Transparency:** Clear data lineage through saved artifacts

## Migration Path

- Existing `egregora process` command remains unchanged
- New stage commands are additive
- Users can choose workflow: monolithic (`process`) or staged (new commands)
