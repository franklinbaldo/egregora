# Banner Generation Feature

## Overview

AI-powered banner/cover image generation for blog posts using Gemini 2.5 Flash Image model. The writer agent can optionally call the `generate_banner` tool after creating a post to generate a striking, concept-driven banner image.

## How It Works

1. **Writer agent creates a post** using the `write_post` tool
2. **Writer agent calls `generate_banner`** with post slug, title, and summary
3. **Gemini 2.5 Flash Image generates** a 1024x1024 banner based on the post content
4. **Banner is saved** to `output/media/banners/banner-{slug}.{ext}`
5. **Relative path returned** for inclusion in post frontmatter

## Architecture

### Components

- **`src/egregora/generation/banner/generator.py`**: Core banner generation logic
  - `BannerGenerator` class wraps Gemini 2.5 Flash Image API
  - `generate_banner_for_post()` convenience function
  - Streaming API for efficient image generation

- **`src/egregora/generation/writer/tools.py`**: Tool declaration
  - `generate_banner` function declaration with schema
  - Available to writer agent via function calling

- **`src/egregora/generation/writer/handlers.py`**: Tool handler
  - `_handle_generate_banner_tool()` processes the tool call
  - Error handling and path management
  - Returns success/failure response to LLM

- **`src/egregora/generation/writer/core.py`**: Integration
  - Dispatches `generate_banner` tool calls to handler
  - Connected to main writer loop

### Tool Schema

```python
{
  "name": "generate_banner",
  "description": "Generate a cover/banner image for a blog post using AI. Use this AFTER writing a post.",
  "parameters": {
    "post_slug": "URL-friendly slug of the post",
    "title": "Post title to base the banner design on",
    "summary": "Brief summary or key themes to inform the banner design"
  }
}
```

### Design Principles

The banner generator is instructed to create:

- **Modern, minimalist design** - Clean, professional aesthetic
- **Abstract/conceptual** - Not literal depictions
- **Bold, striking visuals** - Eye-catching compositions
- **Suitable for blog headers** - Optimized for banner format
- **Legible when scaled** - Works at various sizes
- **Professional and engaging** - Publication-quality images

## Usage

### API Key Setup

The banner generator requires a Gemini API key with access to image generation:

```bash
export GEMINI_API_KEY="your-api-key"
# or
export GOOGLE_API_KEY="your-api-key"
```

### Writer Agent Usage

The writer agent automatically has access to the `generate_banner` tool. The LLM decides when to use it based on the post content and context.

**Example LLM workflow:**

1. Agent writes a post: `write_post(content="...", metadata={...})`
2. Agent decides to generate banner: `generate_banner(post_slug="my-post", title="My Post", summary="...")`
3. Agent receives response: `{"status": "success", "banner_path": "../media/banners/banner-my-post.png"}`

### Programmatic Usage

```python
from pathlib import Path
from egregora.generation.banner import generate_banner_for_post

banner_path = generate_banner_for_post(
    post_title="The Future of AI",
    post_summary="Exploring trends in artificial intelligence and machine learning",
    output_dir=Path("output/media/banners"),
    slug="future-of-ai",
    api_key="your-api-key"  # optional, reads from env
)

if banner_path:
    print(f"Banner generated: {banner_path}")
else:
    print("Banner generation failed")
```

## Implementation Details

### Image Generation Process

1. **Prompt construction**: System instruction + user prompt with title/summary
2. **Streaming generation**: Uses `generate_content_stream()` for efficiency
3. **Image extraction**: Finds `inline_data` parts with image MIME types
4. **File saving**: Writes binary data to disk with proper extension
5. **Path resolution**: Returns relative path for use in markdown

### System Instruction

The banner generator uses a detailed system instruction to guide image generation:

> "You are a senior editorial illustrator for a modern blog. Your job is to translate an article into a striking, concept-driven cover/banner image that is legible at small sizes, brand-consistent, and accessible. Create minimalist, abstract representations that capture the essence of the article without literal depictions. Use bold colors, clear composition, and modern design principles."

### Error Handling

- **API key missing**: Raises `ValueError` during initialization
- **Generation failure**: Returns `None` and logs error
- **Tool handler errors**: Returns error response to LLM
- **Missing parameters**: Handled gracefully with defaults

### Output Format

- **Image size**: 1024x1024 (1K mode for blog banners)
- **Format**: Determined by API (typically PNG or JPEG)
- **Filename pattern**: `banner-{slug}.{ext}`
- **Location**: `output/media/banners/`

## Configuration

Currently, banner generation is always available when the Gemini API key is set. The LLM decides when to use it.

**Future enhancement**: Add configuration flag to enable/disable:

```yaml
# mkdocs.yml
extra:
  egregora:
    enable_banners: true  # future option
```

## Testing

### Manual Testing

```bash
# Generate a test banner
uv run python -c "
from pathlib import Path
from egregora.generation.banner import generate_banner_for_post

result = generate_banner_for_post(
    post_title='Test Post',
    post_summary='A test blog post about AI',
    output_dir=Path('test_output'),
    slug='test-post'
)
print(f'Result: {result}')
"
```

### Integration Testing

Banner generation is tested as part of the full pipeline:

```bash
# Run egregora with banner generation enabled
uv run egregora process export.zip --output ./output
```

## Limitations

1. **API dependency**: Requires Gemini 2.5 Flash Image access
2. **Cost**: Each banner generation is an API call
3. **Quality variance**: AI-generated images may vary in quality
4. **No manual control**: LLM decides when to generate banners
5. **Single attempt**: No automatic retry on poor generation

## V3 Feed-Based Banner Generation

The v3 implementation introduces a **feed-to-feed transformation** approach for banner generation, enabling batch processing and better integration with the Atom protocol.

### Architecture

**Input**: Feed where each `Entry` represents a banner generation task
**Output**: Feed where each `Entry` is a generated banner (MEDIA document)

### Components

- **`src/egregora/agents/banner/feed_generator.py`**: Feed-based generator
  - `FeedBannerGenerator`: Main class for feed-to-feed transformation
  - `BannerTaskEntry`: Extracts task parameters from feed entries
  - `BannerGenerationResult`: Wraps generation outcomes

### Task Entry Schema

Each input entry should contain:

```python
Entry(
    id="task:unique-id",
    title="Post Title for Banner",
    summary="Post summary or description",
    internal_metadata={
        "slug": "post-slug",      # Optional: Post slug for banner naming
        "language": "pt-BR"        # Optional: Language code (default: pt-BR)
    }
)
```

### Output Documents

Successful generations produce MEDIA documents:

```python
Document(
    doc_type=DocumentType.MEDIA,
    title="Banner: Post Title",
    content="<base64-encoded-image>",
    content_type="image/png",
    internal_metadata={
        "task_id": "task:unique-id",
        "generated_at": "2025-12-06T17:00:00Z"
    }
)
```

Failed generations produce NOTE documents with error details.

### Usage Example

```python
from datetime import UTC, datetime
from egregora.agents.banner.feed_generator import FeedBannerGenerator
from egregora_v3.core.types import Entry, Feed, Author

# Create task feed
task_feed = Feed(
    id="urn:tasks:banner:batch1",
    title="Banner Generation Tasks",
    updated=datetime.now(UTC),
    entries=[
        Entry(
            id="task:1",
            title="The Future of AI",
            summary="Exploring artificial intelligence trends",
            updated=datetime.now(UTC),
            internal_metadata={"slug": "future-of-ai"},
        ),
        Entry(
            id="task:2",
            title="Machine Learning Basics",
            summary="Introduction to ML concepts",
            updated=datetime.now(UTC),
            internal_metadata={"slug": "ml-basics"},
        ),
    ],
    authors=[Author(name="System")],
    links=[],
)

# Generate banners
generator = FeedBannerGenerator()
result_feed = generator.generate_from_feed(task_feed)

# Process results
for entry in result_feed.entries:
    if entry.doc_type == DocumentType.MEDIA:
        print(f"✓ Generated: {entry.title}")
    elif entry.doc_type == DocumentType.NOTE:
        print(f"✗ Failed: {entry.title}")
```

### Processing Modes

#### Sequential Mode (Default)

Processes each task entry one at a time:

```python
result_feed = generator.generate_from_feed(task_feed, batch_mode=False)
```

- **Pros**: Simple, reliable, immediate feedback
- **Cons**: Slower for large batches
- **Use when**: Processing small batches or needing immediate results

#### Batch Mode (Future)

Uses Gemini Batch API for efficient bulk processing:

```python
from egregora.agents.banner.gemini_provider import GeminiImageGenerationProvider

provider = GeminiImageGenerationProvider()
generator = FeedBannerGenerator(provider=provider)
result_feed = generator.generate_from_feed(task_feed, batch_mode=True)
```

- **Pros**: Cost-effective, efficient for large batches
- **Cons**: Higher latency, async processing
- **Use when**: Processing 10+ banners, cost is a concern

### Integration with Atom Feeds

The feed-based approach enables:

1. **Feed Distribution**: Publish task feeds via Atom for distributed processing
2. **Result Aggregation**: Combine result feeds from multiple workers
3. **Threading**: Link banners to original posts using `in_reply_to`
4. **Syndication**: Export results to feed readers and aggregators

### Error Handling

The generator creates NOTE documents for failures:

```python
Document(
    doc_type=DocumentType.NOTE,
    title="Error: Post Title",
    content="Failed to generate banner: API error",
    content_type="text/plain",
    internal_metadata={
        "task_id": "task:1",
        "error_code": "GENERATION_FAILED",
        "error_message": "API error details..."
    }
)
```

This ensures the output feed always has the same number of entries as the input feed, making it easy to correlate results with tasks.

### Testing

Run feed generator tests:

```bash
uv run pytest tests/unit/agents/banner/test_feed_generator.py -v
```

## Future Enhancements

- [ ] Configuration flag to enable/disable banner generation
- [ ] Style templates (photography, illustration, abstract, etc.)
- [ ] Banner regeneration command for existing posts
- [ ] Caching to avoid regenerating identical banners
- [ ] Quality feedback loop using post engagement metrics
- [ ] Multiple banner options with LLM selection
- [ ] Custom system instructions per blog configuration
- [ ] Fallback to stock images on generation failure
- [ ] True batch API support for GeminiImageGenerationProvider
- [ ] Feed-based task queue integration
- [ ] Distributed banner generation across multiple workers

## References

- [Gemini 2.5 Flash Image Documentation](https://ai.google.dev/gemini-api/docs/image-generation)
- [Material for MkDocs Blog Plugin](https://squidfunk.github.io/mkdocs-material/plugins/blog/)
- [Writer Architecture](../guide/architecture.md#writer-agent)
