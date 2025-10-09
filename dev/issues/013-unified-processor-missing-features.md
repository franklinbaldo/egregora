# Issue #013: UnifiedProcessor Missing Core Features

## Priority: High
## Effort: High
## Type: Feature Gap

## Problem Description

The UnifiedProcessor is missing several core features that users expect based on configuration options. Features are documented and configurable but not implemented in the new processor.

**Missing features:**
1. **Content Enrichment** - URL analysis and summaries
2. **RAG Context** - Historical newsletter search
3. **Previous Newsletter Loading** - Continuity context
4. **Media Extraction** - Images/videos from ZIP files
5. **URL Preservation** - Shared links in conversations

## Current Behavior

### Non-Functional Configuration
```toml
[enrichment]
enabled = true  # ← Has no effect in UnifiedProcessor

[rag]
enabled = true  # ← Has no effect in UnifiedProcessor

[media]
media_dir = "media"  # ← Media not extracted
```

### TODOs in Code
```python
# src/egregora/processor.py:224-230
llm_input = build_llm_input(
    group_name=source.name,
    timezone=self.config.timezone,
    transcripts=[(target_date, transcript)],
    previous_newsletter=None,  # TODO: integrate previous newsletter
    enrichment_section=None,  # TODO: integrate enrichment
    rag_context=None,  # TODO: integrate RAG
)
```

## Expected Behavior

### 1. Content Enrichment Integration

```python
def _generate_newsletter(self, source, transcript, target_date):
    # Extract and enrich URLs if enabled
    enrichment_section = None
    if self.config.enrichment.enabled:
        from .enrichment import ContentEnricher
        from .cache_manager import CacheManager
        
        cache = CacheManager(self.config.cache.cache_dir) if self.config.cache.enabled else None
        enricher = ContentEnricher(self.config.enrichment, cache_manager=cache)
        
        # Extract URLs and enrich them
        results = await enricher.enrich_transcript(transcript)
        if results:
            enrichment_section = enricher.format_enrichment_section(results)
```

### 2. RAG Context Integration

```python
def _generate_newsletter(self, source, transcript, target_date):
    # Get RAG context if enabled
    rag_context = None
    if self.config.rag.enabled:
        from .rag import search_newsletters
        rag_context = search_newsletters(transcript, self.config)
```

### 3. Media Extraction Integration

```python
def _process_source(self, source, days):
    # Extract media from ZIP exports
    if self.config.media.enabled:
        from .media_extractor import MediaExtractor
        extractor = MediaExtractor(self.config.media.media_dir)
        
        for target_date in target_dates:
            # Extract media for this date
            all_media = {}
            for export in source.exports:
                media_files = extractor.extract_media_from_zip(
                    export.zip_path, 
                    target_date
                )
                all_media.update(media_files)
            
            # Get transcript and replace media references
            transcript = extract_transcript(source, target_date)
            transcript = MediaExtractor.replace_media_references(transcript, all_media)
```

### 4. Previous Newsletter Loading

```python
def _generate_newsletter(self, source, transcript, target_date):
    # Load previous newsletter for continuity
    previous_newsletter = None
    prev_date = target_date - timedelta(days=1)
    prev_path = self.config.posts_dir / source.slug / "daily" / f"{prev_date}.md"
    
    if prev_path.exists():
        previous_newsletter = prev_path.read_text()
```

## Implementation Plan

### Phase 1: Core Integration
- [ ] Integrate enrichment system
- [ ] Add previous newsletter loading
- [ ] Implement media extraction

### Phase 2: Advanced Features
- [ ] RAG context integration
- [ ] URL preservation fixes
- [ ] Performance optimizations

### Phase 3: Testing & Polish
- [ ] Comprehensive test coverage
- [ ] Configuration validation
- [ ] Error handling improvements

## Expected Benefits

1. **Feature Completeness**: All documented features work
2. **User Expectations**: Config options have actual effect
3. **Enhanced Newsletters**: Rich content with links, media, context
4. **Architecture Consistency**: New processor matches old capabilities

## Acceptance Criteria

- [ ] `ContentEnricher` called when `enrichment.enabled = true`
- [ ] URLs extracted and analyzed with caching
- [ ] Media files extracted and linked in newsletters
- [ ] Previous newsletters loaded for context
- [ ] RAG search provides historical context
- [ ] Configuration flags control all features
- [ ] Performance comparable to old pipeline
- [ ] Full test coverage for all integrations

## Files to Modify

- `src/egregora/processor.py` - Main integration work
- `tests/test_unified_processor_features.py` - Feature verification
- `docs/configuration.md` - Updated feature documentation

## Related Issues

- #012: Privacy leak (must be fixed first)
- #007: Media Handling Enhancement
- #005: Performance & Scalability