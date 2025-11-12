# Security & Code Quality Audit Report
## Egregora: src/egregora/core/, src/egregora/database/, src/egregora/config/

**Scan Date**: 2025-11-11  
**Scope**: Security vulnerabilities, dead code, missing validation, type safety, unclear abstractions, database query vulnerabilities

---

## CRITICAL SEVERITY - SQL Injection Vulnerabilities

### 1. Unquoted Table Names in DuckDB Operations

**File**: `/home/user/egregora/src/egregora/database/storage.py`  
**Lines**: 145-151, 149-151, 259, 261  
**Severity**: CRITICAL  
**Issue Type**: SQL Injection

**Description**:
Table names are embedded directly in SQL strings without quoting. An attacker could inject SQL by providing a malicious table name. DuckDB identifiers should be quoted with double quotes.

**Code Examples**:

```python
# Line 145 - Unquoted table name
sql = f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet('{parquet_path}')"

# Line 149 - Unquoted table name
sql = f"""
    CREATE TABLE IF NOT EXISTS {name} AS SELECT * FROM read_parquet('{parquet_path}') WHERE 1=0;
    INSERT INTO {name} SELECT * FROM read_parquet('{parquet_path}')
"""

# Line 259 - Unquoted identifier in DROP VIEW
self.conn.execute(f"DROP VIEW IF EXISTS {name}")

# Line 261 - Unquoted identifier in DROP TABLE
self.conn.execute(f"DROP TABLE IF EXISTS {name}")
```

**Fix**: Use the `quote_identifier()` function from schemas.py (line 355) which is designed for this purpose.

```python
sql = f"CREATE OR REPLACE TABLE {quote_identifier(name)} AS SELECT * FROM read_parquet('{parquet_path}')"
```

---

### 2. SQL Injection in ViewRegistry

**File**: `/home/user/egregora/src/egregora/database/views.py`  
**Lines**: 126-128, 137-140, 184-185, 222, 265, 267  
**Severity**: CRITICAL  
**Issue Type**: SQL Injection

**Description**:
View names are not quoted when building SQL statements. Multiple methods are vulnerable.

**Code Examples**:

```python
# Line 126-128 - DROP VIEW without quoting
self.connection.execute(f"DROP VIEW IF EXISTS {view.name}")
if view.materialized:
    self.connection.execute(f"DROP TABLE IF EXISTS {view.name}")

# Line 137-140 - CREATE TABLE without quoting
self.connection.execute(f"CREATE TABLE IF NOT EXISTS {view.name} AS {view.sql}")

# Line 184-185 - DROP TABLE without quoting
self.connection.execute(f"DROP TABLE IF EXISTS {view.name}")
self.connection.execute(f"CREATE TABLE {view.name} AS {view.sql}")

# Line 222 - SELECT without quoting
return self.connection.execute(f"SELECT * FROM {name}").fetchdf()

# Line 265, 267 - DROP without quoting
self.connection.execute(f"DROP TABLE IF EXISTS {view.name}")
self.connection.execute(f"DROP VIEW IF EXISTS {view.name}")
```

**Fix**: Quote all identifiers using a quoting function.

---

### 3. SQL Injection in Schema Utility Functions

**File**: `/home/user/egregora/src/egregora/database/schemas.py`  
**Lines**: 386, 413-414, 449-452  
**Severity**: CRITICAL  
**Issue Type**: SQL Injection

**Description**:
Column and table names are directly interpolated into ALTER TABLE and CREATE INDEX statements.

**Code Examples**:

```python
# Line 386 - Unquoted table and column names
conn.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT pk_{table_name} PRIMARY KEY ({column_name})")

# Line 413-414 - Unquoted table and column names
conn.execute(
    f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET GENERATED {generated} AS IDENTITY"
)

# Line 449-452 - Unquoted identifiers in CREATE INDEX
conn.execute(
    f"CREATE INDEX IF NOT EXISTS {index_name} "
    f"ON {table_name} USING HNSW ({column_name}) "
    "WITH (metric = 'cosine')"
)
```

**Fix**: Quote all identifiers.

---

## HIGH SEVERITY - Validation & Error Handling Issues

### 4. Missing SQL Injection Prevention Despite Comments

**File**: `/home/user/egregora/src/egregora/database/storage.py`  
**Lines**: 145, 151  
**Severity**: HIGH  
**Issue Type**: Misleading Security Comment

**Description**:
Code contains `# nosec B608` comments claiming the table name is "validated by caller", but no validation is visible in the method signature or implementation. This creates false confidence in security.

```python
# Line 145-151
sql = f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_parquet('{parquet_path}')"  # nosec B608 - name validated by caller
```

The comment claims validation but `name` is a raw parameter from the caller with no validation shown.

---

### 5. Misleading Security Comments in register_common_views()

**File**: `/home/user/egregora/src/egregora/database/views.py`  
**Lines**: 376, 402, 418, 434  
**Severity**: HIGH  
**Issue Type**: Misleading Security Comment

**Description**:
Comments claim `table_name` is "constant from caller" and safe, but `table_name` is actually a function parameter that could be user-controlled.

```python
# Line 376
sql=f"""
    SELECT
        author,
        COUNT(*) as message_count,
        ...
    FROM {table_name}  # <-- parameter, not constant!
""",  # nosec B608 - table_name is constant from caller
```

This is factually incorrect - `table_name` is passed as a parameter to `register_common_views()` at line 354.

---

### 6. Overly Broad Exception Handling

**File**: `/home/user/egregora/src/egregora/database/storage.py`  
**Line**: 109  
**Severity**: HIGH  
**Issue Type**: Error Handling

**Description**:
Reading tables with a bare `except Exception` clause masks specific errors.

```python
# Line 109
try:
    return self.ibis_conn.table(name)
except Exception as e:  # Too broad - catches all exceptions
    msg = f"Table '{name}' not found in database"
    logger.exception(msg)
    raise ValueError(msg) from e
```

**Impact**: Makes debugging harder and could mask programming errors.

**Fix**: Catch specific exception types (e.g., `except (AttributeError, KeyError, ValueError) as e`).

---

### 7. Bare except Clause in Config Loader

**File**: `/home/user/egregora/src/egregora/config/loader.py`  
**Lines**: 75-78  
**Severity**: HIGH  
**Issue Type**: Error Handling

**Description**:
The loader has a bare `except Exception` that masks the real error.

```python
# Lines 75-78
except Exception:
    logger.exception("Invalid config in %s", config_path)
    logger.warning("Creating default config due to validation error")
    return create_default_config(site_root)
```

This silently creates default config on ANY error, even programming mistakes.

**Fix**: Catch specific exceptions like `pydantic.ValidationError`.

---

### 8. Silent Validation Failure Masking

**File**: `/home/user/egregora/src/egregora/database/validation.py`  
**Lines**: 309-316  
**Severity**: HIGH  
**Issue Type**: Error Handling

**Description**:
Runtime validation failures are silently logged as warnings instead of being propagated.

```python
# Lines 309-316
except Exception as e:
    if isinstance(e, SchemaError):
        raise
    # Runtime validation failure is not critical - schema validation passed
    # Log warning but don't fail (execution issues with memtable, etc.)
    import logging
    logging.getLogger(__name__).warning("IR v1 runtime validation skipped due to execution error: %s", e)
```

**Problem**: If validation fails due to actual data issues, not execution issues, the error is silently hidden. This could hide schema violations during development.

---

## MEDIUM SEVERITY - Type Safety & Data Integrity Issues

### 9. Shallow Dictionary Copy Exposes Shared References

**File**: `/home/user/egregora/src/egregora/core/document.py`  
**Lines**: 145, 172-173  
**Severity**: MEDIUM  
**Issue Type**: Data Integrity

**Description**:
The `with_parent()` and `with_metadata()` methods use shallow copy of metadata dict. If metadata contains nested dicts or lists, they remain shared.

```python
# Line 145 - with_parent()
metadata=self.metadata.copy(),  # Shallow copy!

# Line 172-173 - with_metadata()
new_metadata = self.metadata.copy()  # Shallow copy!
new_metadata.update(updates)
```

**Example Problem**:
```python
doc1 = Document(metadata={"nested": {"value": 1}})
doc2 = doc1.with_metadata(title="New")
doc2.metadata["nested"]["value"] = 999  # Also changes doc1!
```

**Fix**: Use `copy.deepcopy()` for nested structures.

**Note**: Since Document is frozen (line 40), this is less critical, but still a potential issue for mutable nested objects.

---

### 10. No Explicit Error Handling for JSON Parsing

**File**: `/home/user/egregora/src/egregora/database/validation.py`  
**Lines**: 175-183  
**Severity**: MEDIUM  
**Issue Type**: Error Handling

**Description**:
`load_ir_v1_lockfile()` declares it can raise `json.JSONDecodeError` but doesn't handle it explicitly.

```python
# Line 183
return json.loads(lockfile_path.read_text())
```

If JSON is malformed, the exception propagates. While declared in docstring, explicit error handling would be better:

```python
try:
    return json.loads(lockfile_path.read_text())
except json.JSONDecodeError as e:
    msg = f"Invalid JSON in {lockfile_path}: {e}"
    raise ValueError(msg) from e
```

---

### 11. Silent Environment Variable Defaults

**File**: `/home/user/egregora/src/egregora/config/site.py`  
**Lines**: 42-49  
**Severity**: MEDIUM  
**Issue Type**: Configuration Validation

**Description**:
The YAML loader's `!ENV` tag handler silently returns empty strings for missing environment variables.

```python
# Lines 40-50
def _construct_env(loader: yaml.SafeLoader, node: yaml.Node) -> str:
    if isinstance(node, yaml.ScalarNode):
        var_name = loader.construct_scalar(node)
        return os.environ.get(var_name, "")  # Silent default!
    if isinstance(node, yaml.SequenceNode):
        items = loader.construct_sequence(node)
        if not items:
            return ""
        var_name = items[0]
        default = items[1] if len(items) > 1 else ""
        return os.environ.get(var_name, default)  # Silent default!
    return ""
```

**Problem**: If a required environment variable is missing, the user gets an empty string with no warning. This could cause downstream errors that are hard to debug.

**Example**:
```yaml
google_api_key: !ENV GOOGLE_API_KEY
```

If `GOOGLE_API_KEY` is not set, silently becomes empty string, causing cryptic API errors later.

---

## LOW SEVERITY - Code Quality & Clarity Issues

### 12. Redundant Type Conversion

**File**: `/home/user/egregora/src/egregora/config/site.py`  
**Line**: 156  
**Severity**: LOW  
**Issue Type**: Code Quality

**Description**:
Unnecessarily converts Path to string and back.

```python
# Line 156
docs_path = Path(str(docs_setting))
```

Could be simplified to:
```python
docs_path = Path(docs_setting)
```

---

### 13. Inconsistent Type Hints

**File**: `/home/user/egregora/src/egregora/database/storage.py`  
**Line**: 282  
**Severity**: LOW  
**Issue Type**: Type Safety

**Description**:
The `__exit__` method uses `# type: ignore[no-untyped-def]` comment instead of proper type hints.

```python
# Line 282
def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
```

Should be:
```python
def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
```

---

### 14. Bare Except in Views Registry

**File**: `/home/user/egregora/src/egregora/database/views.py`  
**Lines**: 130, 279  
**Severity**: LOW  
**Issue Type**: Error Handling

**Description**:
Some error handlers catch exceptions too broadly.

```python
# Line 130
except duckdb.Error:
    pass  # View doesn't exist, that's fine
```

This silently passes for ANY DuckDB error, not just "view doesn't exist".

---

## SUMMARY TABLE

| Severity | Category | Count | Files |
|----------|----------|-------|-------|
| CRITICAL | SQL Injection | 13 | storage.py, views.py, schemas.py |
| HIGH | Error Handling & Validation | 4 | storage.py, loader.py, validation.py, views.py |
| MEDIUM | Type Safety & Config | 3 | document.py, validation.py, site.py |
| LOW | Code Quality | 3 | storage.py, views.py, site.py |
| **TOTAL** | | **23** | |

---

## IMMEDIATE ACTION ITEMS

1. **URGENT**: Fix all SQL injection vulnerabilities by quoting identifiers
2. **HIGH**: Remove or correct misleading `# nosec` comments in storage.py and views.py
3. **HIGH**: Replace bare `except Exception` with specific exception types
4. **MEDIUM**: Add deep copy in Document.with_parent() and with_metadata()
5. **MEDIUM**: Add validation for environment variables in YAML loader
6. **LOW**: Add proper type hints to context manager methods

---

## POSITIVE FINDINGS

✅ **Good practices observed**:
- Use of frozen dataclasses with slots (document.py)
- Parameterized queries in some places (storage.py line 224)
- Comprehensive schema validation with Pydantic V2 (config/schema.py)
- Proper use of logging throughout
- Type hints on most functions
- Configuration validation with constraints (RAGConfig.top_k with ge=1, le=20)

