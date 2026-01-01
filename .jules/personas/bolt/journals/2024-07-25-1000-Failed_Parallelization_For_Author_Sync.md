---
title: "⚡ Parallelization Overhead Outweighs I/O Gains"
date: 2024-07-25
author: "Bolt"
emoji: "⚡"
type: journal
---

## ⚡ 2024-07-25 - Summary

**Observation:** The `sync_authors_from_posts` function in `src/egregora/utils/authors.py` reads and parses every markdown file in a directory to collect author information. This sequential, I/O-bound loop was a clear candidate for performance optimization, especially for sites with a large number of posts.

**Action:**
1.  I followed a strict TDD approach, first writing a new performance test, `tests/unit/utils/test_authors_performance.py`, to establish a baseline.
2.  The initial test failed due to improper state management between benchmark runs. I corrected this by adding a cleanup function to ensure each run was independent.
3.  The baseline performance was established at approximately **65ms** for processing 500 files.
4.  I implemented a parallelized version of the function using `concurrent.futures.ThreadPoolExecutor`.
5.  I ran the benchmark again, and the result was a significant performance *degradation*, with the mean execution time increasing to **~226ms**.
6.  I reverted the production code to its original, more performant sequential implementation.

**Reflection:** This was a critical lesson in the overhead of parallelization. While `ThreadPoolExecutor` is well-suited for I/O-bound tasks, the cost of creating, managing, and synchronizing threads outweighed the benefits for this specific workload, which involves many small, fast file reads. The original, simpler sequential loop was more efficient. The most valuable outcome of this task was not an optimization but the creation of a new, robust benchmark test that will prevent future performance regressions in this critical, I/O-heavy function. Always benchmark to verify assumptions; sometimes, the simplest solution is the fastest.