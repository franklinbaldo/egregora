# API Rate Limiting and Quota Management

## Problem

The Egregora pipeline does not handle API rate limits gracefully, leading to processing failures when Gemini API quotas are exceeded.

## Current Behavior

When hitting rate limits, the pipeline fails with:
```
ClientError: 429 RESOURCE_EXHAUSTED. 
'You exceeded your current quota, please check your plan and billing details.'
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 15
Please retry in 54.381632892s.
```

## Impact

- **Processing Failure**: Complete pipeline stops on rate limit
- **Data Loss Risk**: No partial results saved when hitting limits
- **Poor UX**: No graceful degradation or retry mechanisms
- **Free Tier Limitations**: 15 requests per minute is very restrictive

## Observed Quota Limits

- **Free Tier**: 15 requests per minute per model
- **Model Used**: `gemini-2.5-flash-lite` 
- **Retry Delay**: 54+ seconds suggested

## Required Improvements

### 1. Rate Limit Detection and Retry
```python
def handle_rate_limit(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            if e.status_code == 429:
                retry_delay = extract_retry_delay(e)
                log.warning(f"Rate limited, waiting {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### 2. Progressive Processing
- Process messages in batches
- Save intermediate results
- Resume from last successful point

### 3. Quota Management
- Track API call usage
- Estimate processing time based on quotas
- Warn users about quota limitations upfront

### 4. Configuration Options
- Configurable retry attempts
- Batch size limits
- Rate limiting delays

## Technical Considerations

### Cost Estimation
- Calculate total API calls needed before starting
- Show estimated cost and time
- Allow users to proceed or adjust scope

### Fallback Strategies
- Reduce message scope when hitting limits
- Skip optional enrichment when quota low
- Process only most recent messages

### Monitoring
- Log API usage statistics
- Track quota consumption patterns
- Report processing efficiency

## Files Affected

- `src/egregora/generator.py` (post generation)
- `src/egregora/enrichment.py` (link enrichment) 
- `src/egregora/processor.py` (orchestration)
- Configuration files for retry settings

## Priority

**High** - This blocks real-world usage for users on free tier, which is likely most users initially.

## Related Issues

- Cost optimization
- Processing time estimation
- Partial result persistence
- User experience during long processing