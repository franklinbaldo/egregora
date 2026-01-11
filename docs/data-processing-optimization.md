# Data Processing Optimization Plan

Last updated: 2024-07-25

## Current Data Processing Patterns

The codebase currently uses a mix of declarative Ibis-based transformations and imperative, row-by-row Python processing. The WhatsApp input adapter (`src/egregora/input_adapters/whatsapp/parsing.py`) exemplifies the latter, reading a chat log line-by-line in a Python loop to parse messages. While effective, this pattern is inefficient for large files as it fails to leverage the parallel processing capabilities of the underlying DuckDB engine.

## Identified Inefficiencies

- **WhatsApp Parser:** The `_parse_whatsapp_lines` function in `src/egregora/input_adapters/whatsapp/parsing.py` reads and processes the chat export one line at a time. This is a significant bottleneck, especially for large chat histories. The process involves multiple Python function calls per line, which is much slower than a single, vectorized database operation.

## Prioritized Optimizations

1.  **Vectorize the WhatsApp Parser:** Refactor the WhatsApp parser to use a declarative, vectorized approach with Ibis. The goal is to read the raw text file directly into DuckDB and apply regex and string functions in a single query to parse all messages at once. This will significantly improve performance by letting the database engine handle the heavy lifting.

## Completed Optimizations

_No optimizations completed yet._

## Optimization Strategy

My strategy is to systematically identify and replace imperative, row-by-row data processing loops with declarative, vectorized Ibis expressions. The core principle is to "let the database do the work," pushing as much of the transformation logic as possible into the DuckDB engine. This will not only improve performance but also make the data processing logic more concise and easier to maintain.
