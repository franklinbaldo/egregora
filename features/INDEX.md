# Egregora BDD Features Index

This index provides a complete overview of all BDD features for Egregora, organized by hierarchy and importance.

## Quick Reference

| Level | Category | Description | Feature Count |
|-------|----------|-------------|---------------|
| 01 | Core | Critical features defining core value | 3 |
| 02 | Essential | Important capabilities for basic function | 3 |
| 03 | Advanced | Value-add features enhancing quality | 4 |
| 04 | Specialized | Features for specific use cases | 4 |
| 05 | Utility | Supporting and troubleshooting features | 2 |

**Total Features: 16**

---

## 01-core/ - Critical Features

These features represent the fundamental value proposition of Egregora.

### 01-chat-to-blog-transformation.feature
Transform chaotic group chat history into structured blog posts.

**Key Scenarios:**
- Transform simple and multi-topic conversations
- Handle long conversations with segmentation
- Filter by date range
- Configure window sizes (messages, hours, days)
- Use overlapping windows for continuity
- Resume interrupted transformations
- Force refresh all content
- Handle empty or trivial conversations
- Preserve message metadata
- Normalize timezones

### 02-content-generation.feature
AI-powered generation of engaging, coherent blog posts from conversations.

**Key Scenarios:**
- Generate blog posts with structured sections
- Support custom languages
- Apply custom writing instructions
- Use contextual awareness from previous posts
- Handle mixed languages and media references
- Process technical and casual conversations
- Manage URL references
- Handle insufficient content gracefully
- Adjust creativity with temperature settings
- Track annotations linking content to messages
- Represent multiple viewpoints fairly
- Use custom prompt templates

### 03-static-site-output.feature
Generate browsable static websites from blog posts.

**Key Scenarios:**
- Generate complete website structure
- Browse posts chronologically
- View individual posts with full formatting
- Search for content
- Display embedded media (images, videos)
- Navigate site structure
- Responsive mobile display
- Subscribe via RSS feeds
- Support dark mode
- Handle large numbers of posts efficiently
- Include metadata for SEO and social sharing
- Browse by category or tag
- Export for web hosting
- Serve locally for preview
- Customize appearance

---

## 02-essential/ - Important Features

Essential capabilities needed for the application to function effectively.

### 01-input-parsing.feature
Parse chat exports from various platforms correctly.

**Key Scenarios:**
- Parse WhatsApp exports (with and without media)
- Parse multi-file exports
- Detect format automatically
- Support multiple formats (WhatsApp, Slack, Telegram, Discord)
- Handle corrupted or unusual data
- Parse very large exports efficiently
- Normalize timestamps and timezones
- Extract metadata (group name, participants)
- Distinguish system messages
- Handle deleted messages
- Preserve threaded conversations
- Validate parsed data structure
- Merge multiple exports
- Handle various date formats

### 02-media-management.feature
Properly handle images, videos, and other media files.

**Key Scenarios:**
- Extract images, videos, audio, and documents
- Optimize images for web display
- Maintain aspect ratios
- Handle duplicate media efficiently
- Reference media in generated posts
- Handle missing or corrupted files
- Support various formats (JPEG, PNG, GIF, WebP, MP4, etc.)
- Generate video thumbnails
- Respect size limits
- Organize media by type
- Associate media with messages
- Sanitize unusual filenames
- Download external media references
- Preserve upload timestamps
- Include captions

### 03-site-initialization.feature
Easy setup of new blog projects.

**Key Scenarios:**
- Initialize new project with defaults
- Create project in empty or new directory
- Generate configuration and directory structure
- Set up site metadata
- Create customizable template files
- Integrate with version control
- Optionally include sample content
- Validate initialization success
- Configure models, prompts, database
- Set privacy and timezone settings
- Provide post-initialization guidance
- Detect and handle reinitialization
- Create secure API key configuration

---

## 03-advanced/ - Value-Add Features

Advanced capabilities that enhance content quality and value.

### 01-content-evaluation.feature
Identify the best quality content through AI-powered ranking.

**Key Scenarios:**
- Evaluate post quality systematically
- Rank posts from best to worst
- Compare two posts with reasoning
- Perform pairwise comparisons efficiently
- Calculate ranking scores (e.g., ELO-based)
- Display top-ranked posts
- View comparison history
- Re-evaluate after changes
- Handle ties in ranking
- Evaluate fairly regardless of length
- Use multiple criteria (clarity, engagement, coherence)
- Limit evaluation to post subsets
- View detailed feedback per post
- Export rankings
- Persist rankings across sessions
- Provide confidence scores
- Re-rank with new posts
- Identify quality patterns

### 02-content-enrichment.feature
Automatically add context and descriptions to URLs and media.

**Key Scenarios:**
- Enrich URLs with previews (title, description)
- Enrich multiple URLs per post
- Generate image descriptions for accessibility
- Generate video descriptions
- Handle enrichment failures gracefully
- Batch process enrichments
- Skip already enriched content
- Refresh existing enrichments
- Configure enrichment for specific types
- Set batch thresholds
- Handle rate limiting
- Extract web page metadata
- Generate media captions
- Enrich audio descriptions
- Cache enrichment results
- Display enrichment status
- Run enrichment asynchronously
- Prioritize top posts
- Generate alt text for accessibility

### 03-author-profiling.feature
Generate AI-powered insights about chat participants.

**Key Scenarios:**
- Generate profiles for individual authors
- Generate profiles for all participants
- Identify main topics of interest
- Analyze communication patterns
- Track author evolution over time
- Highlight significant contributions
- Create multiple profiles per author
- Focus profiles on specific areas
- Include statistics (message count, frequency)
- Identify collaboration patterns
- Handle low-activity and high-activity authors
- Organize profiles in dedicated section
- Link profiles to related posts
- Update profiles with new data
- Respect privacy in profiles
- Generate comparative profiles
- Include visual elements
- Generate unique profile identifiers

### 04-contextual-memory.feature
Use conversation history to improve content generation (RAG).

**Key Scenarios:**
- Index conversation history
- Retrieve related previous discussions
- Use retrieved context in generation
- Avoid repeating previous content
- Configure retrieval count (top-k)
- Weight recent contexts higher
- Index incrementally as posts are generated
- Search indexed content by topic
- Handle queries with no relevant context
- Retrieve across multiple posts
- Update index after content refresh
- Disable contextual memory when desired
- Export and import index
- Measure retrieval quality
- Handle very large history
- Retrieve context for author profiles
- Index multiple languages
- Optimize index storage
- Provide source attribution

---

## 04-specialized/ - Specialized Features

Features addressing specific use cases and requirements.

### 01-privacy-controls.feature
Control how personal information is handled and protected.

**Key Scenarios:**
- Enable full author anonymization
- Anonymize selectively by author
- Opt out specific authors from content
- Preserve anonymization across sessions
- Generate readable anonymous identifiers
- Strip sensitive metadata from media
- Redact or hash sensitive information
- Control privacy at different levels
- Anonymize while preserving relationships
- Configure privacy per content type
- Warn when publishing anonymized content
- Export and import privacy settings
- Apply privacy retroactively
- Maintain privacy in author profiles
- Handle mixed anonymization
- Provide privacy audit
- Redact specific patterns (addresses, phones)
- Allow manual privacy review
- Document privacy in site metadata
- Disable privacy temporarily for testing

### 02-command-system.feature
Include special commands in chat messages to control blog generation.

**Key Scenarios:**
- Execute avatar commands
- Execute bio commands
- Process multiple commands from different authors
- Ignore invalid commands
- Parse commands with multiple parameters
- Create announcements for executed commands
- List available commands
- Execute commands with privacy mode
- Override previous commands
- Process commands chronologically
- Handle malformed syntax
- Execute commands affecting multiple authors
- Track command execution history
- Rollback commands
- Execute commands once or allow overrides
- Display command help inline
- Authenticate command senders
- Process commands during incremental updates
- Export command configuration
- Filter commands from regular content

### 03-configuration-management.feature
Customize behavior and output through comprehensive configuration.

**Key Scenarios:**
- View default configuration
- Change AI models for different agents
- Configure custom writing instructions
- Set output language
- Configure windowing parameters
- Enable/disable specific features
- Configure timezone for timestamps
- Set maximum token limits
- Customize prompt templates
- Configure batch processing thresholds
- Enable/disable RAG
- Configure RAG retrieval parameters
- Set privacy and anonymization options
- Configure API keys securely
- Validate configuration on load
- Reset to defaults
- Export and import configuration
- Override configuration via CLI
- Configure different models per agent
- Set temperature for generation
- Configure logging verbosity
- Define custom date formats
- Lock configuration
- Configure multiple output directories
- Migrate configuration between versions

### 04-resume-checkpoint.feature
Resume interrupted operations without losing progress.

**Key Scenarios:**
- Save checkpoints automatically during processing
- Resume after interruption from last checkpoint
- Use resume flag to continue
- Skip completed windows on resume
- Update checkpoint incrementally
- Handle configuration changes on resume
- Clear checkpoints after completion
- Manually delete checkpoint to restart
- Handle corrupted checkpoints
- Detect input file changes
- Display resume progress accurately
- Checkpoint enrichment progress
- Checkpoint evaluation progress
- Force restart ignoring checkpoints
- Resume multiple parallel operations
- Handle windowing changes
- Store checkpoint metadata
- Resume after system failure
- Warn before overwriting checkpoint
- Reprocess partial window completion

---

## 05-utility/ - Supporting Features

Utility features that support development and troubleshooting.

### 01-diagnostics.feature
Diagnose issues and validate project health.

**Key Scenarios:**
- Run basic health check
- Validate configuration file
- Check API key validity
- Verify database integrity
- Check for missing dependencies
- Validate input file format
- Check storage space
- Verify site structure
- Test model connectivity
- Check for orphaned files
- Validate media files
- Check checkpoint validity
- Run diagnostics in verbose mode
- Generate diagnostic report
- Test enrichment service connectivity
- Verify RAG index health
- Check version compatibility
- Validate prompt templates
- Check privacy configuration consistency
- Test site build process
- Recommend optimization opportunities

### 02-demo-generation.feature
Quickly generate sample blogs for evaluation.

**Key Scenarios:**
- Generate complete demo blog
- Use default settings for quick demo
- Generate in custom directory
- Include sample conversations
- Demonstrate enrichment features
- Showcase different post types
- Generate minimal or full-featured demos
- Include sample media
- Provide demo documentation
- Generate demo in custom language
- Demonstrate ranking
- Generate demo quickly
- Include sample author profiles
- Demonstrate privacy features
- Demonstrate RAG functionality
- Regenerate with different settings
- Export demo for sharing
- Clean up demo after evaluation
- Generate demo with custom sample data

---

## Implementation Notes

### For BDD Framework Integration

These features are designed to be used with BDD testing frameworks:

```python
# Using pytest-bdd
from pytest_bdd import scenarios, given, when, then

scenarios('features/01-core/01-chat-to-blog-transformation.feature')

@given("I have initialized a blog project")
def blog_project():
    # Setup code
    pass
```

```python
# Using behave
from behave import given, when, then

@given("I have initialized a blog project")
def step_impl(context):
    # Setup code
    pass
```

### Coverage Goals

- **Critical Path:** 100% coverage of 01-core features
- **Essential:** 90%+ coverage of 02-essential features
- **Advanced:** 70%+ coverage of 03-advanced features
- **Specialized:** 50%+ coverage of 04-specialized features
- **Utility:** 40%+ coverage of 05-utility features

### Prioritization for Implementation

1. Start with 01-core features (MVP)
2. Add 02-essential features (functional completeness)
3. Implement 03-advanced features (quality and value)
4. Add 04-specialized features (specific needs)
5. Implement 05-utility features (support and polish)

---

*This index represents the complete BDD specification for Egregora as of January 2026.*
