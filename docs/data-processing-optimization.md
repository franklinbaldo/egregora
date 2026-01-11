# Data Processing Optimization Plan

Last updated: 2024-07-29

## Current Data Processing Patterns

The codebase currently exhibits a mix of declarative Ibis-based processing and imperative, row-by-row Python processing. A key area of concern is the input adapters, specifically the WhatsApp parser, which reads a chat log line-by-line, applies regex, and uses a stateful builder to construct messages. This pattern is common in data processing code that has not been optimized for a vectorized query engine and can lead to significant performance bottlenecks with large input files. It prevents the database from leveraging its parallel execution and optimized data layout capabilities.

## Identified Inefficiencies

1.  **WhatsApp Parser (`src/egregora/input_adapters/whatsapp/parsing.py`):**
    - **Problem:** The `_parse_whatsapp_lines` function iterates through each line of a chat file in a Python loop. For each line, it executes a regex match. If it's a new message, it finalizes the previous one and starts a new entry in a `MessageBuilder`. If it's a continuation line, it appends it to the current message.
    - **Evidence:** The use of a `for line in source.lines():` loop combined with a stateful `MessageBuilder` class is a clear indicator of imperative, row-by-row processing. The presence of `@lru_cache` on helper functions like `_parse_message_date` is a workaround for the performance cost of calling these functions repeatedly in a loop, which wouldn't be necessary in a vectorized approach.
    - **Impact:** This approach is CPU-bound and memory-inefficient. It cannot be parallelized by the database engine and scales poorly with the size of the input chat log.
    - **Note (2024-07-29):** An attempt was made to refactor this parser to a vectorized Ibis pipeline. However, the complexity of robust error handling for malformed lines within the vectorized model proved to be intractable. The optimization was reverted in favor of the current, safer imperative implementation. See commit history for details.

## Prioritized Optimizations

*(No optimizations in progress.)*

## Completed Optimizations

*(No optimizations completed yet.)*

## Optimization Strategy

My strategy for this codebase is to systematically identify and eliminate imperative data processing loops, replacing them with declarative, vectorized Ibis expressions.

1.  **Prioritize Ingestion:** Focus on input adapters first, as inefficiencies here have a cascading effect on the entire pipeline.
2.  **Leverage Ibis:** Push as much logic as possible into Ibis expressions to let DuckDB handle the execution optimization. This includes string parsing, data type conversion, and aggregations.
3.  **Strict TDD:** For any refactoring, ensure existing tests pass before and after the change. If tests don't exist, write them first to capture the existing behavior.
4.  **Measure Everything:** Use existing performance tests or create new ones to quantify the impact of every optimization. This will validate the changes and inform future prioritization.
