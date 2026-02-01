# Troubleshooting Guide

This guide covers common issues you might encounter when using Egregora and how to resolve them.

## 🛑 Common Errors

### API Rate Limiting (429 Error)

**Symptoms:**
- Error message: `Quota exceeded for quota metric 'Queries' and limit 'Queries per minute' of service 'generativelanguage.googleapis.com'`
- Process pauses frequently with "Rate limit exceeded" logs.

**Cause:**
You are hitting the usage limits of the Google Gemini API. The free tier has a limit of 15 requests per minute (RPM).

**Solutions:**
1.  **Wait and Retry:** Egregora automatically handles retries, so often you just need to be patient.
2.  **Use Multiple Keys:** You can provide multiple API keys separated by commas to increase your effective rate limit.
    ```bash
    export GOOGLE_API_KEY="key1,key2,key3"
    ```
3.  **Adjust Quota:** Lower the configured RPM in `.egregora.toml` (if you created one) or use the default safe settings.

### Database Locked

**Symptoms:**
- Error message: `duckdb.IOException: IO Error: Could not open database because the lock file exists`
- The process fails immediately on startup.

**Cause:**
Another Egregora process is currently running or a previous process crashed without cleaning up the lock file.

**Solutions:**
1.  **Check for Running Processes:** Ensure no other terminal is running `egregora`.
2.  **Remove Lock File:** If no process is running, delete the lock file manually:
    ```bash
    rm .egregora/pipeline.duckdb.wal
    ```

### LanceDB Permission Issues

**Symptoms:**
- Error message: `OSError: [Errno 13] Permission denied: '.egregora/lancedb/...'`

**Cause:**
File permissions prevent Egregora from writing to the vector database directory, common in Docker or multi-user environments.

**Solutions:**
1.  **Fix Permissions:** Grant write access to the directory:
    ```bash
    chmod -R u+w .egregora/lancedb/
    ```

## 🔧 Environment Issues

### Python Version Mismatch

**Symptoms:**
- Error during installation: `Requires-Python >=3.12, but you have ...`

**Solution:**
Egregora requires Python 3.12 or newer. Update your Python installation.
- **Mac:** `brew install python`
- **Windows:** Download from python.org

### "Command not found: uv"

**Symptoms:**
- You cannot run `uv` commands.

**Solution:**
Ensure `uv` is installed and in your PATH.
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## ❓ Still Stuck?

If you can't find a solution here:
1.  Check the [GitHub Issues](https://github.com/franklinbaldo/egregora/issues) to see if others have the same problem.
2.  Open a new issue with your error log and steps to reproduce.
