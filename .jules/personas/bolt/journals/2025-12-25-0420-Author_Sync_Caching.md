---
title: "⚡ Author Sync Caching"
date: 2025-12-25
author: "Bolt"
emoji: "⚡"
type: journal
---

## ⚡ 2025-12-25 - Caching for `sync_authors_from_posts`
**Observation:** The `sync_authors_from_posts` function in `src/egregora/utils/filesystem.py` was repeatedly scanning every markdown file on every run, even if the files hadn't changed. This created a significant I/O bottleneck, especially for large sites.

**Action:**
1.  I wrote a `pytest-benchmark` test to establish a baseline performance metric for the function when no new authors are present. The initial median time was ~215ms for 500 files.
2.  I implemented a caching mechanism using a `.authors.cache.json` file. The cache stores the authors for each file, keyed by the file path and its last modification time (`mtime`).
3.  On subsequent runs, the function now first checks the `mtime` of each file. If it matches the cached value, the author data is read from the cache, avoiding a full file read and frontmatter parsing.
4.  I re-ran the benchmark, which showed the median time for the cached run dropped to ~155ms, a performance improvement of ~28%.

**Reflection:** This was a successful optimization that targeted a clear I/O bottleneck. The file system is often a source of performance issues, and caching based on modification times is a classic and effective solution. In the next iteration, I should investigate other areas where file system access could be optimized, such as image processing or other metadata aggregation steps. There may be other opportunities to apply similar caching strategies to reduce redundant work.
