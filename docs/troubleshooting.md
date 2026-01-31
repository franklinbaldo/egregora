# Troubleshooting Guide

This guide covers common issues you might encounter when using Egregora.

## API & Model Issues

### 429 Too Many Requests (Quota Exceeded)

**Symptom:** The pipeline stops with an error mentioning "Quota exceeded" or "429".

**Cause:** You have hit the rate limit for your Google Gemini API key. The free tier has strict limits (RPM/TPM).

**Solution:**
1.  **Wait and Retry:** The pipeline is designed to be resumed. Just run the command again later.
2.  **Adjust Rate Limits:** In your `.egregora.toml`, lower the requests per minute:
    ```toml
    [models.rate_limits]
    rpm = 2  # Lower this value (default might be 15 or 60)
    ```
3.  **Use Paid Tier:** The paid tier for Gemini has significantly higher limits.

### "Prompt Too Large" Error

**Symptom:** `PromptTooLargeError: Window size X tokens exceeds model limit Y`.

**Cause:** A specific conversation window contains too much text for the AI model to process at once.

**Solution:**
Egregora usually handles this automatically by splitting the window. If it fails:
1.  **Reduce Window Size:** In `.egregora.toml`:
    ```toml
    [pipeline]
    step_size = 50  # Reduce from default (e.g., 100)
    step_unit = "messages"
    ```
2.  **Switch Model:** Use a model with a larger context window (e.g., `gemini-1.5-pro` instead of `flash`).

## Database Issues

### "Database is Locked" (DuckDB)

**Symptom:** Error `duckdb.IOException: IO Error: Cannot open file... database is locked`.

**Cause:** Another Egregora process is running or didn't close properly, holding the lock on `.egregora/pipeline.duckdb`.

**Solution:**
1.  **Check Running Processes:** Ensure no other `egregora` commands are running.
2.  **Remove Lock File:** If no process is running, delete the `.egregora/pipeline.duckdb.wal` file (Write-Ahead Log) manually.
    ```bash
    rm .egregora/pipeline.duckdb.wal
    ```

### RAG Initialization Failures

**Symptom:** Errors related to `lancedb` or `embeddings`.

**Cause:** Corrupted vector store or missing dependencies.

**Solution:**
1.  **Rebuild Index:** You can safe delete the RAG database to force a rebuild (this will take time to re-index).
    ```bash
    rm -rf .egregora/rag/
    ```
2.  **Check Dependencies:** Ensure you have installed all extras:
    ```bash
    uv sync --all-extras
    ```

## Environment Issues

### "Command not found: egressora"

**Solution:** Ensure you are running commands via `uv` or have activated the virtual environment.
```bash
uv run egregora ...
```
Or activate:
```bash
source .venv/bin/activate
egregora ...
```

### Missing Fonts or Assets

**Symptom:** `MkDocs` build warnings about missing files.

**Solution:**
Ensure you are running the build from the project root.
```bash
uv run mkdocs build
```

## Getting Help

If you're still stuck:
1.  Check the [FAQ](faq.md).
2.  Search [GitHub Issues](https://github.com/franklinbaldo/egregora/issues).
3.  Open a new issue with your error log.
