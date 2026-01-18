---
title: "⚡ Optimize Author Extraction"
date: 2026-01-16
author: "bolt"
emoji: "⚡"
type: journal
---

# ⚡ Bolt: Author Extraction Optimization

## Observation
I observed that `sync_authors_from_posts` in `src/egregora/knowledge/profiles.py` was previously identified as a bottleneck. While previous journals suggested it was optimized, my analysis showed that the overhead of creating `pathlib.Path` objects for every file in a large directory tree was significant. The existing implementation used `posts_dir.rglob("*.md")`, which instantiates a `Path` object for every file found.

Profiling revealed that `pathlib.Path` instantiation and related methods accounted for a noticeable portion of the execution time (~20%) when scanning 1000 files.

## Action
I optimized the `sync_authors_from_posts` function by replacing `pathlib.rglob` with `os.walk`. This change allows the function to iterate over file paths as strings, avoiding the overhead of `Path` object creation for each file.

To support this, I refactored `extract_authors_from_post` to accept both `pathlib.Path` and `str` types for the `md_file` argument. This ensures backward compatibility while enabling the performance optimization in the hot loop.

I also fixed a blocker in `tests/features/voting.feature` where an unsupported `Because` keyword was preventing the benchmark suite from running.

## Reflection
The optimization yielded a measurable improvement. In my micro-benchmarks, `os.walk` was ~15-20% faster than `pathlib.rglob` for simple iteration. The full benchmark `test_sync_authors_from_posts_benchmark` showed a mean execution time of ~28ms for 500 files, which is a solid improvement over the previous ~33ms (and much better than the original ~160ms baselines from older journals).

This confirms that for high-frequency loops involving file system traversal, working with raw string paths is more performant than using the higher-level `pathlib` abstractions, even though `pathlib` is generally preferred for its API elegance.

## Next Steps
Monitor for other areas where `pathlib.Path` usage in tight loops might be causing similar overhead. Static site generation and other bulk file processing tasks are prime candidates for this type of optimization.
