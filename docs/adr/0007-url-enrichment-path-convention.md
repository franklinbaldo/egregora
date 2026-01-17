# ADR-0007: URL Enrichment Path Convention

## Status
Accepted

## Context
URL enrichment documents are posts generated from shared URLs (YouTube videos, Spotify playlists, arXiv papers, Wikipedia articles, etc.). Currently, these are placed directly in `docs/posts/`, mixing with writer-generated blog posts.

URLs should be treated as a type of media, similar to images, videos, and audio.

## Decision
URL enrichment documents go inside the media directory as a new media type:

**URL**: `/posts/media/urls/{slug}`
**Filesystem**: `docs/posts/media/urls/{slug}.md`

### Media Directory Structure
```
docs/posts/media/
├── images/
├── videos/
├── audio/
├── documents/
└── urls/        ← URL enrichments go here
```

### Metadata Requirements
URL enrichment documents have:
```yaml
type: url_enrichment
source_url: {original_url}
```

### Examples
| Source | Path |
|--------|------|
| YouTube video | `posts/media/urls/youtube-quantum-computing-tutorial.md` |
| Spotify playlist | `posts/media/urls/spotify-techno-wave-playlist.md` |
| arXiv paper | `posts/media/urls/arxiv-quantum-computing-paper.md` |
| Wikipedia | `posts/media/urls/wikipedia-itsukushima-shrine.md` |

## Consequences

### Easier
- Consistent: URLs are treated as media like images/videos
- Clear media directory structure
- Easy to find all enriched content in one place

### Harder
- URL enricher must route to media/urls path

## Related
- ADR-0001: Media and Routing Conventions
