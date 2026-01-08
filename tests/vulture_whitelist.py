"""Vulture whitelist for known false positives.

This file tells vulture about intentional "unused" code that shouldn't be flagged.
Only includes v3 code and test mocks - v2 code should be kept clean with actual fixes.
"""


def _whitelist() -> None:
    """Hold vulture whitelist references."""

    # Use a dummy object to reference attributes without triggering ruff errors
    class _Placeholder:
        exc_type = None
        exc_val = None
        exc_tb = None
        file = None
        posts_created = None

    _ = _Placeholder()

    # Pure: __exit__ method signature (required by context manager protocol)
    # src/egregora/infra/adapters/rss.py
    _.exc_type  # noqa: B018
    _.exc_val  # noqa: B018
    _.exc_tb  # noqa: B018

    # Tests: Mock method parameters used as keyword arguments
    # tests/unit/agents/banner/test_gemini_provider.py
    _.file  # noqa: B018

    # Protocols: Method parameters used in protocol signatures but not in implementations
    # src/egregora/data_primitives/protocols.py:226
    # src/egregora/output_adapters/base.py:275
    _.posts_created  # noqa: B018

    # Tests: Fixtures and mocks in cache tests
    # tests/unit/utils/test_enrichment_cache.py
    _.mock_backend  # noqa: B018
    _.cache  # noqa: B018
