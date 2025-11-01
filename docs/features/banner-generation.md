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

## Future Enhancements

- [ ] Configuration flag to enable/disable banner generation
- [ ] Style templates (photography, illustration, abstract, etc.)
- [ ] Banner regeneration command for existing posts
- [ ] Caching to avoid regenerating identical banners
- [ ] Quality feedback loop using post engagement metrics
- [ ] Multiple banner options with LLM selection
- [ ] Custom system instructions per blog configuration
- [ ] Fallback to stock images on generation failure

## References

- [Gemini 2.5 Flash Image Documentation](https://ai.google.dev/gemini-api/docs/image-generation)
- [Material for MkDocs Blog Plugin](https://squidfunk.github.io/mkdocs-material/plugins/blog/)
- [Writer Architecture](../guides/architecture.md#5-generation-writer)
