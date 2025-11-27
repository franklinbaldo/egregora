# Writer API

The writer agent generates blog-ready narratives from enriched conversation windows.

## Responsibilities
- Assemble prompt context using XML conversation payloads.
- Leverage cache tiers to avoid unnecessary LLM calls.
- Emit deterministic output assets for publication adapters.

Further sections will document prompt variables, cache controls, and extension hooks.
