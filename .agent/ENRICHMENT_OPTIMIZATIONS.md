# Egregora Enrichment Optimizations

Detailed specifications for low-priority optimizations to reduce API rate limiting and improve enrichment efficiency.

---

## 1. Multi-Image Batch Enrichment (Medium Priority)

### Goal
Send all images in a single API call to Gemini, returning a dict with enrichment results for each image. This reduces 12 API calls → 1 call.

### Current Behavior
- Each image is enriched individually via `_execute_media_individual()` in `src/egregora/agents/enricher.py`
- Each call takes ~20 seconds with rate limiting

### Proposed Implementation

1. **Add config flag** in `src/egregora/config/settings.py`:
```python
class EnrichmentSettings(BaseModel):
    batch_images: bool = Field(default=True, description="Batch all images in one LLM call")
```

2. **Create batch enrichment method** in `src/egregora/agents/enricher.py`:
```python
def _execute_media_batch_single_call(self, tasks: list[dict]) -> dict[str, MediaEnrichmentResult]:
    """Send all images in one API call, return dict by filename."""
    # Load all image bytes
    images = [(task["filename"], self._load_media_bytes(task)) for task in tasks]
    
    # Build prompt with all images
    prompt = """For each image, provide:
    - slug: short descriptive slug (e.g., "sunset-beach")
    - description: 2-3 sentence description
    - alt_text: accessibility description
    
    Return JSON dict where keys are filenames:
    {"image1.jpg": {"slug": "...", "description": "...", "alt_text": "..."}, ...}
    """
    
    # Single API call with all images as BinaryContent
    result = genai_client.generate_content([prompt] + [BinaryContent(data=img) for _, img in images])
    
    return json.loads(result.text)
```

3. **Key files to modify**:
   - `src/egregora/agents/enricher.py` - `_process_media_batch()` method (~line 1100)
   - `src/egregora/config/settings.py` - `EnrichmentSettings` class

### Token Estimation
- Each image ≈ 256 tokens
- Gemini context: 1M+ tokens
- Can fit ~4000 images in one call

---

## 2. Vision Model Fallback for OpenRouter (Low Priority)

### Goal
When Gemini returns 429, fall back to free OpenRouter **vision** models (currently fetches 'text' models).

### Current Behavior
- `src/egregora/models/model_fallback.py` fetches `modality='text'`
- Media enrichment needs `modality='image'` or `modality='vision'`

### Proposed Implementation

1. **Modify OpenRouter model fetching** to support vision:
```python
def get_free_vision_models() -> list[str]:
    """Fetch free OpenRouter models that support image input."""
    response = httpx.get("https://openrouter.ai/api/v1/models")
    models = response.json()["data"]
    return [m["id"] for m in models if "image" in m.get("architecture", {}).get("modality", "")]
```

2. **Key files to modify**:
   - `src/egregora/models/model_fallback.py` - add `get_free_vision_models()`
   - `src/egregora/agents/enricher.py` - use vision models for media

---

## 3. OpenRouter Model Cycling on 429 (Low Priority)

### Goal
When one OpenRouter model returns 429, immediately try the next free model instead of waiting.

### Current Behavior
- Retry with same model after delay
- All models share rate limits on some providers

### Proposed Implementation

1. **Add model cycling logic**:
```python
class ModelCycler:
    def __init__(self, models: list[str]):
        self.models = models
        self.current_idx = 0
    
    def next_model(self) -> str:
        model = self.models[self.current_idx]
        self.current_idx = (self.current_idx + 1) % len(self.models)
        return model
    
    async def call_with_fallback(self, prompt, **kwargs):
        for _ in range(len(self.models)):
            try:
                return await self.call(self.next_model(), prompt, **kwargs)
            except RateLimitError:
                continue
        raise AllModelsRateLimited()
```

2. **Key files to modify**:
   - `src/egregora/models/model_fallback.py`

---

## 4. URL Screenshot Enrichment (Low Priority)

### Goal
Instead of fetching URL content as text, screenshot the page and use vision model for richer context.

### Current Behavior
- URL enrichment uses text-based analysis
- Loses visual context (images, layout, styling)

### Proposed Implementation

1. **Add screenshot capability** using playwright/selenium:
```python
async def screenshot_url(url: str) -> bytes:
    """Capture URL screenshot for vision enrichment."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=10000)
        screenshot = await page.screenshot(full_page=True)
        await browser.close()
        return screenshot
```

2. **Integrate with enricher**:
   - Screenshot URL → pass to vision model → get rich description
   - Fall back to text-based if screenshot fails

3. **Key files to modify**:
   - New file: `src/egregora/utils/screenshot.py`
   - `src/egregora/agents/enricher.py` - `_execute_url_enrichments()`

4. **Dependencies to add**:
   - `playwright` in pyproject.toml

---

## 5. Video Batch Enrichment (Low Priority)

### Goal
Similar to multi-image batch, but for videos.

### Considerations
- Videos are larger (tokens depend on duration)
- Gemini supports video but may need chunking
- May need to extract keyframes instead of full video

### Proposed Implementation
1. Extract keyframes from video (ffmpeg)
2. Send keyframes as images in batch call
3. Combine descriptions into video summary

---

## Priority Order

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| Medium | Multi-image batch | High (12→1 calls) | Medium |
| Low | Vision model fallback | Medium | Low |
| Low | Model cycling on 429 | Medium | Low |
| Low | URL screenshots | Low | Medium |
| Low | Video batch | Low | High |
