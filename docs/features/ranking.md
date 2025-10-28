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

Rankings are stored in a **DuckDB database** for fast updates and efficient queries:

### Primary Storage: `rankings.duckdb`

DuckDB database with two tables:

**`elo_ratings` table:**

| Column | Type | Description |
|--------|------|-------------|
| `post_id` | VARCHAR | Post filename stem (PRIMARY KEY) |
| `elo_global` | DOUBLE | Current ELO rating (starts at 1500) |
| `games_played` | INTEGER | Number of comparisons |
| `last_updated` | TIMESTAMP | Last update timestamp |

**`elo_history` table:**

| Column | Type | Description |
|--------|------|-------------|
| `comparison_id` | VARCHAR | UUID for this comparison (PRIMARY KEY) |
| `timestamp` | TIMESTAMP | When comparison occurred |
| `profile_id` | VARCHAR | Profile that judged |
| `post_a` | VARCHAR | First post ID |
| `post_b` | VARCHAR | Second post ID |
| `winner` | VARCHAR | "A" or "B" |
| `comment_a` | VARCHAR | Feedback on post A (max 250 chars) |
| `stars_a` | INTEGER | Star rating for A (1-5) |
| `comment_b` | VARCHAR | Feedback on post B (max 250 chars) |
| `stars_b` | INTEGER | Star rating for B (1-5) |

**Why DuckDB?**
- **Fast updates**: No read-modify-write of entire file (10-50x faster than Parquet)
- **ACID transactions**: Safe concurrent access
- **Indexed queries**: Fast comment lookups by post ID
- **SQL interface**: Flexible analytics
- **Already in stack**: Used for RAG vector store

### Optional Export: Parquet Files

Export to Parquet for sharing or external analytics:

```bash
egregora rank --site_dir ./blog --comparisons 10 --export_parquet
```

Creates:
- `rankings/elo_ratings.parquet`
- `rankings/elo_history.parquet`

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

Using rankings database: ./my-blog/rankings/rankings.duckdb

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
│ Primary storage:                             │
│ • rankings.duckdb - DuckDB database          │
│                                              │
│ Tip: Use --export_parquet to create Parquet │
│ files for sharing/analytics                  │
╰──────────────────────────────────────────────╯
```

## Use Cases

### 1. Homepage "Top Posts" Section

Display highest-rated posts:

```python
from pathlib import Path
from egregora.ranking import RankingStore

# Connect to rankings database
store = RankingStore(Path("rankings"))

# Get top 10 posts (with at least 5 games for confidence)
top_posts = store.get_top_posts(n=10, min_games=5)
print(top_posts)
```

### 2. Quality Filtering

Filter out low-quality content:

```python
# Get all ratings as an Ibis Table
ratings = store.get_all_ratings()

# Posts with ELO < 1400 after 5+ games are candidates for editing/archiving
low_quality = ratings.filter(
    (ratings.games_played >= 5) & (ratings.elo_global < 1400)
)

# Convert to pandas when you need to display the result
low_quality_pd = low_quality.execute()
```

### 3. Content Analytics

Analyze what makes posts successful:

```python
# Get all comments for a specific post
post_feedback = store.get_comments_for_post("2025-01-15-my-post")
print(post_feedback)

# Or get full history as an Ibis Table for complex analytics
history = store.get_all_history()

# See what different profiles thought
profile_patterns = history.group_by("profile_id").agg(
    history.stars_a.mean().alias("avg_stars")
)
```

### 4. Editorial Decisions

Guide which posts to promote:

```python
# High-confidence winners (10+ games, ELO > 1600)
top_candidates = store.get_top_posts(n=100, min_games=10)
featured_worthy = top_candidates.filter(top_candidates.elo_global > 1600)
```

### 5. Direct SQL Queries (Advanced)

For complex analytics, query DuckDB directly:

```python
import duckdb

conn = duckdb.connect("rankings/rankings.duckdb")

# Find posts with highest variance in star ratings (polarizing content)
result = conn.execute("""
    SELECT
        COALESCE(post_a, post_b) as post_id,
        AVG(COALESCE(stars_a, stars_b)) as avg_stars,
        STDDEV(COALESCE(stars_a, stars_b)) as star_variance
    FROM (
        SELECT post_a, stars_a, NULL as post_b, NULL as stars_b FROM elo_history
        UNION ALL
        SELECT NULL, NULL, post_b, stars_b FROM elo_history
    )
    GROUP BY post_id
    HAVING COUNT(*) >= 5
    ORDER BY star_variance DESC
    LIMIT 10
""").fetchdf()

print(result)
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
├── __init__.py          # Public API exports
├── store.py            # DuckDB RankingStore class
├── elo.py              # ELO calculation logic
├── agent.py            # Three-turn LLM agent
└── (future) selection.py  # Advanced selection strategies
```

### Design Decisions

**Why DuckDB instead of Parquet?**
- 10-50x faster updates (no read-modify-write entire file)
- ACID transactions for safe concurrent access
- Indexed queries for fast comment lookups
- SQL interface for flexible analytics
- Already in stack (used for RAG)

**Why line-by-line comments?** Creates rich, conversational feedback instead of isolated scores.

**Why profile impersonation?** Captures diverse perspectives on quality (technical vs. creative vs. generalist readers).

**Why three turns?** Separates decision (winner) from analysis (comments), allowing agent to focus on each task.

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
