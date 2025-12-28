from __future__ import annotations

# Vulture whitelists this file.
# See https://github.com/jendrikseipp/vulture#whitelisting-false-positives

# F-strings in asserts are not detected by vulture
# https://github.com/jendrikseipp/vulture/issues/112
# assert f"foo" == "foo"  # pragma: no cover

# Whitelist unused imports in test_agents_are_dead.py
# These are intentionally unused to test for their absence.
dead_agents = ["EnricherAgent", "WriterAgent"]  # pragma: no cover
dead_agents  # pragma: no cover
