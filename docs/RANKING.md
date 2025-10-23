# Egregora Ranking Agent

The Ranking Agent creates a dynamic ELO ranking system for blog posts using LLM-powered comparisons with profile impersonation.

## Overview

### Three-Turn Conversation Protocol

Each comparison follows a structured three-turn conversation:

1. **Turn 1: Choose Winner** - Agent reads both posts and declares which is better overall
2. **Turn 2: Comment on Post A** - Agent provides detailed feedback on Post A (with existing comments as context)
3. **Turn 3: Comment on Post B** - Agent provides detailed feedback on Post B (with existing comments as context)

### Profile Impersonation

Each comparison randomly selects an author profile to impersonate. The LLM takes on that profile's:
- Reading preferences
- Evaluation criteria
- Communication style

This creates diverse perspectives on post quality, similar to having multiple reviewers.

## Usage

### Basic Ranking

Run a single comparison:

```bash
egregora rank --site_dir ./my-blog
```

### Multiple Comparisons

Build robust rankings by running multiple comparisons:

```bash
# Run 50 comparisons to bootstrap the ranking system
egregora rank --site_dir ./my-blog --comparisons 50
```

### With API Key

```bash
egregora rank \
  --site_dir ./my-blog \
  --comparisons 10 \
  --gemini_key YOUR_API_KEY
```

## Data Storage

Rankings are stored in two append-only Parquet files in `rankings/`:

### `elo_ratings.parquet`

Current ELO scores and game counts:

| Column | Type | Description |
|--------|------|-------------|
| `post_id` | string | Post filename stem |
| `elo_global` | float | Current ELO rating (starts at 1500) |
| `games_played` | int | Number of comparisons |
| `last_updated` | datetime | Last update timestamp |

### `elo_history.parquet`

Full comparison history with comments:

| Column | Type | Description |
|--------|------|-------------|
| `comparison_id` | string | UUID for this comparison |
| `timestamp` | datetime | When comparison occurred |
| `profile_id` | string | Profile that judged |
| `post_a` | string | First post ID |
| `post_b` | string | Second post ID |
| `winner` | string | "A" or "B" |
| `comment_a` | string | Feedback on post A (max 250 chars) |
| `stars_a` | int | Star rating for A (1-5) |
| `comment_b` | string | Feedback on post B (max 250 chars) |
| `stars_b` | int | Star rating for B (1-5) |

## How It Works

### ELO Rating System

Uses standard ELO algorithm:
- **Default rating**: 1500
- **K-factor**: 32
- **Zero-sum**: Winner gains points, loser loses points
- **Diminishing returns**: Less change when outcome is expected

### Post Selection Strategy

Prioritizes posts with fewest comparisons:
- New posts get compared first
- Ensures all posts get baseline ratings
- Focuses on resolving uncertain rankings

### Comment Context

Before commenting, the agent sees all previous comments on that post:

```
**@a1b2c3d4** ⭐⭐⭐⭐⭐ (2025-01-20)
> Deep dive into consensus algorithms. Best technical post I've seen.

**@e5f6g7h8** ⭐⭐⭐ (2025-01-22)
> @a1b2c3d4 I agree it's thorough, but dense for general readers.

**@i9j0k1l2** ⭐⭐⭐⭐ (2025-01-25)
> @e5f6g7h8 True, but the diagrams help a lot. Appreciated the clarity.
```

This creates a **discussion thread** instead of isolated ratings.

## Example Session

```bash
$ egregora rank --site_dir ./my-blog --comparisons 3

Using ratings file: ./my-blog/rankings/elo_ratings.parquet

╭─ Comparison 1 of 3 ──────────────────────────╮
│ Comparison 1 of 3                            │
╰──────────────────────────────────────────────╯

Comparing:
  Post A: 2025-01-15-distributed-systems
  Post B: 2025-01-16-weekend-reflections
  Judge: a1b2c3d4...

Turn 1: Choosing winner...
Winner: Post A

Turn 2: Commenting on Post A...
Comment A: Exceptional technical depth. The consensus algorithm...
Stars A: ⭐⭐⭐⭐⭐

Turn 3: Commenting on Post B...
Comment B: Nice personal reflection but lacks the depth I prefer...
Stars B: ⭐⭐⭐

╭─ Success ────────────────────────────────────╮
│ ✓ Comparison complete!                       │
│                                              │
│ Winner: Post A                               │
│                                              │
│ Updated ELO ratings:                         │
│   Post A: 1516                               │
│   Post B: 1484                               │
╰──────────────────────────────────────────────╯

...

╭─ Session Complete ───────────────────────────╮
│ ✓ Ranking session complete!                  │
│                                              │
│ Comparisons completed: 3                     │
│ Rankings stored in: ./my-blog/rankings       │
│                                              │
│ Files:                                       │
│ • elo_ratings.parquet - Current ELO scores   │
│ • elo_history.parquet - Full history         │
╰──────────────────────────────────────────────╯
```

## Use Cases

### 1. Homepage "Top Posts" Section

Display highest-rated posts:

```python
import polars as pl

# Load ratings
ratings = pl.read_parquet("rankings/elo_ratings.parquet")

# Get top 10 posts (with at least 5 games for confidence)
top_posts = (
    ratings
    .filter(pl.col("games_played") >= 5)
    .sort("elo_global", descending=True)
    .head(10)
)
```

### 2. Quality Filtering

Filter out low-quality content:

```python
# Posts with ELO < 1400 after 5+ games are candidates for editing/archiving
low_quality = (
    ratings
    .filter(
        (pl.col("games_played") >= 5) &
        (pl.col("elo_global") < 1400)
    )
)
```

### 3. Content Analytics

Analyze what makes posts successful:

```python
# Load history with comments
history = pl.read_parquet("rankings/elo_history.parquet")

# Get all comments for a specific post
post_feedback = history.filter(
    (pl.col("post_a") == "2025-01-15-my-post") |
    (pl.col("post_b") == "2025-01-15-my-post")
)

# See what different profiles thought
```

### 4. Editorial Decisions

Guide which posts to promote:

```python
# High-confidence winners (10+ games, ELO > 1600)
featured_worthy = (
    ratings
    .filter(
        (pl.col("games_played") >= 10) &
        (pl.col("elo_global") > 1600)
    )
)
```

## Advanced Features (Future)

### Multi-Dimensional Rankings

Track different aspects:
- Technical depth
- Readability
- Originality
- Engagement

### Integration with Editor Agent

Use ranking feedback to guide autonomous editing:

```python
# Posts with ELO < 1450 get flagged for editing
# Editor agent uses comments to understand what to improve
# Re-rank after editing to validate improvement
```

### Polarization Detection

Identify posts with high variance across profiles:
- Technical readers love it, generalists don't
- Or vice versa

## Best Practices

### Cold Start (New Site)

1. Run 50-100 comparisons initially
2. Ensures all posts get baseline ratings (≈5 games each)
3. Establishes relative quality hierarchy

### Ongoing Maintenance

1. Run 5-10 comparisons weekly
2. Focus on new posts (automatic with fewest-games strategy)
3. Build confidence in rankings over time

### Interpreting Results

- **ELO < 1400**: Consider editing or archiving
- **ELO 1400-1500**: Average quality
- **ELO 1500-1600**: Above average
- **ELO > 1600**: Exceptional (feature these!)

### Confidence Levels

- **< 5 games**: Low confidence (still stabilizing)
- **5-10 games**: Medium confidence
- **> 10 games**: High confidence

## Architecture

### File Structure

```
src/egregora/ranking/
├── __init__.py          # Public API
├── elo.py              # ELO calculation logic
├── agent.py            # Three-turn LLM agent
└── selection.py        # Future: advanced selection strategies
```

### Design Decisions

**Why line-by-line comments?** Creates rich, conversational feedback instead of isolated scores.

**Why profile impersonation?** Captures diverse perspectives on quality (technical vs. creative vs. generalist readers).

**Why three turns?** Separates decision (winner) from analysis (comments), allowing agent to focus on each task.

**Why append-only Parquet?** Full audit trail, time-series analytics, never lose historical context.

## Troubleshooting

### No profiles found

```
Process a WhatsApp export first to create author profiles:
egregora process --zip_file export.zip --output ./my-blog
```

### No posts found

```
Make sure posts/ directory exists and contains .md files
```

### API errors

```
Check GOOGLE_API_KEY is valid:
export GOOGLE_API_KEY=your_key_here
```

## Future Enhancements

1. **Smart selection strategies**: Compare similar-ELO posts, boundary posts
2. **Analytics dashboard**: Visualize ranking trends, comment themes
3. **Editor integration**: Auto-flag low-ranked posts for improvement
4. **Multi-profile consensus**: Track which posts rank well across ALL profiles
5. **Polarization metrics**: Identify posts with high variance in ratings
