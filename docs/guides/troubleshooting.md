# Troubleshooting

Common issues and solutions for Egregora.

## Installation Issues

### Python Version Too Old

**Problem:**
```
ERROR: Egregora requires Python 3.11 or higher
```

**Solution:**
```bash
# Check current version
python --version

# Install Python 3.11+ (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv

# Or on macOS with Homebrew
brew install python@3.11

# Create virtualenv with specific Python version
python3.11 -m venv .venv
source .venv/bin/activate
```

### Pip Install Fails

**Problem:**
```
ERROR: Could not find a version that satisfies the requirement egregora
```

**Solution:**
```bash
# Upgrade pip
pip install --upgrade pip

# Install with verbose output to see errors
pip install egregora -v

# Or install from GitHub directly
pip install git+https://github.com/franklinbaldo/egregora.git
```

## Processing Issues

### No Posts Generated

**Problem:** Processing completes but `posts/` directory is empty

**Possible Causes:**

1. **LLM decided nothing worth writing about**

The LLM has editorial judgment. If messages are mostly noise, it won't create posts.

**Solution:**
- Process a longer date range
- Check that messages contain substantive discussions
- Enable debug mode to see LLM reasoning:
  ```bash
  egregora process --debug --zip_file=export.zip
  ```

2. **Date range outside WhatsApp export**

**Solution:**
```bash
# Check date range in your export
unzip -p export.zip _chat.txt | head -20

# Adjust --from_date / --to_date accordingly
egregora process \
  --zip_file=export.zip \
  --from_date=2025-01-01 \
  --to_date=2025-01-31
```

3. **Timezone mismatch**

**Solution:** Always specify timezone:
```bash
egregora process \
  --timezone='America/Sao_Paulo' \
  --zip_file=export.zip
```

### Wrong Dates in Posts

**Problem:** Messages from Jan 15 appear in Jan 14 post

**Cause:** Timezone mismatch

WhatsApp exports use your phone's local timezone. If you don't specify `--timezone`, messages are interpreted as UTC and may shift to previous/next day.

**Solution:**
```bash
egregora process \
  --timezone='Your/Timezone' \
  --zip_file=export.zip
```

Find your timezone: [List of tz database timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

### API Rate Limit Errors

**Problem:**
```
google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded
```

**Solution:**

1. **Add delays between requests** (already built-in to Egregora)

2. **Process smaller date ranges:**
```bash
# Instead of processing entire year
egregora process --from_date=2025-01-01 --to_date=2025-01-31

# Process one month at a time
```

3. **Disable enrichment** (reduces API calls):
```bash
egregora process --enable_enrichment=False
```

4. **Check your Gemini API quota:**
Visit https://ai.google.dev/ → View quotas

### Invalid API Key

**Problem:**
```
google.api_core.exceptions.Unauthenticated: 401 API key not valid
```

**Solution:**

1. **Check API key is correct:**
```bash
# Test API key
curl -H "x-goog-api-key: YOUR_KEY" \
  https://generativelanguage.googleapis.com/v1/models
```

2. **Ensure API key is set:**
```bash
# Via environment variable
export GOOGLE_API_KEY="your-api-key-here"

# Or pass directly
egregora process --gemini_key="your-api-key-here"
```

3. **Generate new API key:**
Visit https://ai.google.dev/ → Get API key

## WhatsApp Export Issues

### Can't Find _chat.txt in ZIP

**Problem:**
```
ValueError: No _chat.txt found in ZIP file
```

**Cause:** Export may be corrupted or in wrong format

**Solution:**

1. **Check ZIP contents:**
```bash
unzip -l export.zip
# Should contain _chat.txt and media files
```

2. **Re-export from WhatsApp:**
- Open chat → ⋮ → More → Export chat
- Save new ZIP file
- Try again

3. **Check file encoding:**
```bash
file export.zip
# Should be: Zip archive data
```

### Parsing Errors

**Problem:**
```
ParserError: Could not parse message: ...
```

**Cause:** Unusual date format or special characters

**Solution:**

1. **Enable debug mode:**
```bash
egregora process --debug --zip_file=export.zip
```

2. **Check message format:**
```bash
unzip -p export.zip _chat.txt | head -50
# Look for date format
```

3. **Report the issue:**
Open an issue at https://github.com/franklinbaldo/egregora/issues with:
- Sample line that failed to parse
- Your WhatsApp language/region
- Debug output

## Ranking Issues

### No Profiles Found

**Problem:**
```
egregora rank
ERROR: No profiles found in ./profiles
```

**Cause:** Haven't processed WhatsApp export yet

**Solution:**
```bash
# Process export first to generate profiles
egregora process --zip_file=export.zip --output=./my-blog

# Then run ranking
egregora rank --site_dir=./my-blog
```

### No Posts Found

**Problem:**
```
ERROR: No posts found in ./posts
```

**Solution:**

1. **Check posts directory exists:**
```bash
ls -la posts/
```

2. **Ensure posts were generated:**
```bash
egregora process --zip_file=export.zip
```

3. **Check site_dir path:**
```bash
# Specify correct path
egregora rank --site_dir=./my-blog
```

### DuckDB Errors

**Problem:**
```
duckdb.Error: IO Error: Could not open file
```

**Solution:**

1. **Check rankings directory exists:**
```bash
mkdir -p my-blog/rankings
```

2. **Check write permissions:**
```bash
ls -la my-blog/rankings/
```

3. **Remove corrupted database:**
```bash
rm my-blog/rankings/rankings.duckdb
# Run ranking again to recreate
```

## RAG Issues

### No RAG Database Found

**Problem:**
```
FileNotFoundError: rag/vectors.duckdb not found
```

**Cause:** RAG indexing hasn't run yet

**Solution:**
```bash
# Enable enrichment to build RAG index
egregora process \
  --zip_file=export.zip \
  --enable_enrichment=True
```

### Slow RAG Indexing

**Problem:** Indexing 1000+ posts takes hours

**Solution:**

1. **Index incrementally** (only new posts)
2. **Reduce chunk size** (fewer chunks per post)
3. **Process in batches:**
```bash
# Process Jan separately
egregora process --from_date=2025-01-01 --to_date=2025-01-31

# Then Feb
egregora process --from_date=2025-02-01 --to_date=2025-02-28
```

### Poor RAG Retrieval Quality

**Problem:** RAG returns irrelevant results

**Solution:**

1. **Increase top-k** (get more diverse results)
2. **Improve query phrasing**
3. **Ensure high-quality posts in index**
4. **Try broader queries**

## Privacy Issues

### Real Names in Output

**Problem:** Real names appear in generated posts

**Cause:** Bug in anonymization (should not happen)

**Solution:**

1. **Check privacy validation:**
```bash
# Egregora automatically scans for phone numbers
# Check logs for warnings
```

2. **Report immediately:**
This is a critical bug. Open an issue with:
- Sample post (redacted)
- WhatsApp export sample (redacted)
- Steps to reproduce

3. **Manual scrub:**
```bash
# Search for real names in posts
grep -r "REAL_NAME" posts/
```

### Phone Numbers in Posts

**Problem:** Phone numbers appear in content

**Cause:** Privacy validation may have missed it

**Solution:**

1. **Remove manually:**
```bash
# Find and remove
grep -r "+1234567890" posts/
```

2. **Report pattern:**
Open an issue so we can improve validation

## Site Building Issues

### MkDocs Not Found

**Problem:**
```
mkdocs: command not found
```

**Solution:**
```bash
pip install mkdocs-material
```

### Build Errors

**Problem:**
```
ERROR: Config file 'mkdocs.yml' does not exist
```

**Solution:**

1. **Initialize site first:**
```bash
egregora init my-blog
cd my-blog
```

2. **Or create mkdocs.yml manually:**
```yaml
site_name: My Blog

theme:
  name: material

plugins:
  - blog:
      blog_dir: posts
```

### Serve Fails

**Problem:**
```
ERROR: Port 8000 is already in use
```

**Solution:**
```bash
# Use different port
mkdocs serve -a localhost:8001

# Or kill existing process
lsof -ti:8000 | xargs kill
```

## Performance Issues

### Processing Too Slow

**Problem:** Processing takes hours for small dataset

**Possible Causes:**

1. **Enrichment enabled with many URLs**

**Solution:**
```bash
# Disable enrichment
egregora process --enable_enrichment=False
```

2. **Large date range**

**Solution:**
```bash
# Process smaller chunks
egregora process --from_date=2025-01-01 --to_date=2025-01-07
```

3. **Many media files**

**Solution:**
- Export without media from WhatsApp
- Or disable media enrichment

### High API Costs

**Problem:** Gemini API bills are unexpectedly high

**Solution:**

1. **Use date filters:**
```bash
egregora process \
  --from_date=2025-01-01 \
  --to_date=2025-01-31  # Process one month only
```

2. **Disable enrichment:**
```bash
egregora process --enable_enrichment=False
```

3. **Use weekly/monthly periods:**
```bash
egregora process --period=week  # Fewer LLM calls
```

4. **Check token usage:**
Enable debug mode to see token counts:
```bash
egregora process --debug
```

## Editor Issues

### Version Mismatch Errors

**Problem:**
```
{"ok": false, "reason": "version_mismatch"}
```

**Cause:** Using outdated version number in edit calls

**Solution:** Always use latest version from previous tool call:
```python
# After edit_line returns {"new_version": 1}
# Use expect_version=1 for next call
```

### Editor Not Making Changes

**Problem:** Editor calls `finish` without edits

**Solution:**

1. **Add specific instructions:**
```python
custom_instructions = "Fix all typos. Improve clarity in section 2."
```

2. **Check RAG context:**
Ensure RAG database has relevant posts

3. **Enable debug mode:**
See what the editor is thinking

## Getting More Help

### Enable Debug Mode

Most issues can be diagnosed with debug mode:

```bash
egregora process --debug --zip_file=export.zip
```

This shows:
- LLM prompts and responses
- API call details
- Token usage
- Detailed error traces

### Check Logs

Egregora logs to console. Redirect to file:

```bash
egregora process --zip_file=export.zip 2>&1 | tee egregora.log
```

### Open an Issue

If you can't solve the problem:

1. **Gather information:**
   - Egregora version: `pip show egregora`
   - Python version: `python --version`
   - OS: `uname -a`
   - Debug output: `egregora --debug`

2. **Create minimal reproduction:**
   - Smallest WhatsApp export that reproduces issue
   - Exact command that fails
   - Expected vs actual behavior

3. **Open issue:**
   https://github.com/franklinbaldo/egregora/issues/new

### Community Support

- **GitHub Discussions:** https://github.com/franklinbaldo/egregora/discussions
- **Stack Overflow:** Tag questions with `egregora`

## Related Documentation

- [Installation](../getting-started/installation.md) - Setup guide
- [Configuration](configuration.md) - Config options
- [Architecture](architecture.md) - How it works internally
