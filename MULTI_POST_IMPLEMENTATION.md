# Multi-Post Generation Feature

## Overview

This feature enables the LLM to create **multiple separate posts per day** (one for each conversation thread/fio) instead of a single aggregated daily post. The LLM uses function calling to invoke a `write_post` tool for each thread it identifies.

## Architecture

### 1. Function Calling Tool (`src/egregora/tools.py`)

Defines the `write_post` tool declaration for Gemini's function calling API:

```python
write_post(
  title: str,           # Thread title
  content: str,         # Full markdown content with front matter
  participants: list    # UUIDs of participants in this thread
)
```

The tool is automatically provided to the LLM during generation when `use_tools=True`.

### 2. Updated Prompts

**`src/egregora/prompts/system_instruction_tools.md`** - New prompt instructing the LLM to:
- Identify distinct threads in the transcript
- Call `write_post` once per thread
- Include complete front matter YAML in each post
- Follow all existing style rules from `system_instruction_base.md`

### 3. Generator Changes (`src/egregora/generator.py`)

**New method**: `generate_posts(source, context, use_tools=True)`
- Returns `list[dict[str, str]]` with keys: `title`, `content`, `participants`
- Enables function calling when `use_tools=True`
- Extracts multiple `write_post` calls from LLM response
- Fallback: if LLM doesn't use tools, treats text response as single post

**Updated method**: `generate(source, context)`
- Now calls `generate_posts(use_tools=False)` for backward compatibility
- Returns single string (legacy behavior)

**Internal changes**:
- `_build_system_instruction()` accepts `use_tools` parameter
- `_build_generation_config()` accepts optional `tools` parameter
- `_execute_generation_with_tools()` handles function call extraction

### 4. Processor Changes (`src/egregora/processor.py`)

**Updated workflow** in `_process_source()`:
1. Call `generator.generate_posts(source, context, use_tools=True)`
2. Receive list of posts (typically 1-10 per day)
3. For each post:
   - Apply media section (first post only)
   - Ensure front matter
   - Add profile links
   - Format markdown
   - Save with unique filename

**Filename strategy**:
- Single post: `{date}-{slug}.md` (e.g., `2025-01-15-pacificacao-social.md`)
- Multiple posts: `{date}-{sequence:02d}-{slug}.md` (e.g., `2025-01-15-01-frameworks-debate.md`, `2025-01-15-02-ia-article.md`)

The LLM generates a URL-friendly slug for each post, which is then sanitized to ensure:
- Lowercase only
- Hyphens instead of spaces
- No accents or special characters
- Maximum 50 characters

### 5. Tests (`tests/test_multi_post.py`)

Three test scenarios:
1. **Function calling mode**: LLM calls `write_post` multiple times
2. **Fallback mode**: LLM doesn't use tools, system falls back to text
3. **Legacy mode**: `generate()` still returns single string

## Usage

### Default Behavior (Multi-Post)

```python
from egregora.processor import UnifiedProcessor
from egregora.config import PipelineConfig

config = PipelineConfig()
processor = UnifiedProcessor(config)

# Automatically uses multi-post generation
results = processor.process_all(days=7)
```

### Force Legacy Behavior (Single Post)

```python
# In processor, use:
post_text = self.generator.generate(source, context)
# Returns single string instead of list
```

## File Outputs

### Before (Single Post Per Day)
```
docs/blog/posts/
  2025-01-15.md    # All threads combined
  2025-01-16.md
```

### After (Multiple Posts Per Day)
```
docs/blog/posts/
  2025-01-15-01-frameworks-debate.md      # Thread 1: Framework discussion
  2025-01-15-02-product-launch.md         # Thread 2: Product launch
  2025-01-15-03-ia-article.md             # Thread 3: AI article
  2025-01-16-01-pacificacao-social.md
  2025-01-16-02-velocidade-qualidade.md
```

## LLM Behavior

The LLM will:
1. **Analyze** the full transcript
2. **Identify** distinct conversation threads (usually 1-10 per day)
3. **Call `write_post`** once for each thread with:
   - Descriptive title
   - URL-friendly slug (sanitized automatically)
   - Complete markdown content (including YAML front matter)
   - List of participant UUIDs
4. Each post follows the same style rules (Scott Alexander-inspired, concrete hooks, etc.)

## Benefits

1. **Better organization**: Each thread is a standalone post
2. **Improved discoverability**: Readers can find specific topics more easily
3. **Cleaner navigation**: Shorter, focused posts instead of long daily aggregates
4. **Flexibility**: LLM decides optimal thread segmentation
5. **Backward compatible**: Legacy single-post mode still works

## Configuration

No configuration changes needed. The feature works automatically with existing config files.

To disable (use legacy single-post mode):
```python
# Modify processor.py line 1082:
# Change:
generated_posts = self.generator.generate_posts(source, context, use_tools=True)

# To:
post = self.generator.generate(source, context)
# Then adapt the rest of the code for single post
```

## Technical Details

### Function Call Extraction

The generator extracts function calls from Gemini's response:

```python
for candidate in response.candidates:
    for part in candidate.content.parts:
        if hasattr(part, "function_call") and part.function_call:
            if part.function_call.name == "write_post":
                args = part.function_call.args
                post_data = {
                    "title": args.get("title", "Untitled"),
                    "content": args.get("content", ""),
                    "participants": args.get("participants", []),
                }
                posts.append(post_data)
```

### Media Section Handling

Media is attached to the **first post only** to avoid duplication:

```python
if media_section and idx == 0:
    post = f"{post.rstrip()}\n\n## Mídias Compartilhadas\n{media_section}\n"
```

### Profile Updates

Profiles are updated once per day using **all posts combined**:

```python
combined_posts = "\n\n---\n\n".join(p["content"] for p in generated_posts)
self._update_profiles_for_day(
    repository=profile_repository,
    source=source,
    target_date=target_date,
    post_text=combined_posts,
)
```

## Prompt Engineering Notes

The `system_instruction_tools.md` prompt emphasizes:
- **MÚLTIPLOS POSTS POR DIA** (multiple posts per day)
- One post = one thread = one `write_post` call
- Always include complete YAML front matter
- Use only UUIDs that participated in that specific thread
- Follow all style rules from base instruction

## Limitations

1. **API calls**: More tokens used per day (one generation produces multiple posts)
2. **Quota**: Consider adjusting rate limits if processing many days
3. **Filename conflicts**: Multiple runs on same day may need conflict resolution
4. **Media distribution**: All media goes to first post (could be improved)

## Future Enhancements

1. **Smart media distribution**: Attach media to relevant thread instead of first post
2. **Thread merging**: Allow LLM to merge related sub-threads
3. **Custom filename patterns**: Configure naming scheme (date_slug, date_time, etc.)
4. **Thread metadata**: Extract keywords, sentiment, importance from each thread
5. **Cross-thread references**: Link related threads across days
