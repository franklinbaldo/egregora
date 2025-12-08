# Prompting with GRWC

Use the GRWC framework (Goal, Return format, Warnings, Context) to keep prompts short, precise, and repeatable. This page gives ready-to-use templates tailored for Egregora workflows.

## Quick templates

### Full template
```
Goal:
[One sentence stating exactly what you want the model to do.]

Return format:
[Bullets, numbered steps, sections, table, JSON keys, etc.]

Warnings:
[Constraints and guardrails: e.g., no invented data, length limits, cite uncertainty.]

Context dump:
[Audience, constraints, examples, source text, attempts so far.]
```

### Compact template (for fast asks)
```
Goal: … | Return: … | Warnings: … | Context: …
```

## Default guardrails and structure
- **Return format defaults:** bullets or numbered steps; include code blocks when asking for code.
- **Warnings defaults:** "If unsure, say you're unsure"; "Don't invent data or sources"; "Keep it under <N> words".
- **Context defaults:** audience, platform/version (e.g., Python 3.12), constraints (no new deps), and any examples of desired tone/output.

## Starters for common tasks

### Coding tasks
- **Goal:** Refactor or implement a specific function or module without changing behavior unless stated.
- **Return format:** 3–5 bullets summarizing changes + final code block + 2–3 lightweight test suggestions.
- **Warnings:** No new dependencies; keep I/O signatures stable; flag uncertainties explicitly.
- **Context dump:** Language/runtime, style preferences (explicit names, early returns), and relevant snippets or tests.

### Analysis or decision briefs
- **Goal:** Assess whether a change/behavior aligns with a policy, requirement, or target outcome.
- **Return format:** Restate question → relevant framework → pros → cons → concise conclusion (2–4 paragraphs) with risks/unknowns.
- **Warnings:** Do not invent citations; highlight where facts are missing; keep the conclusion balanced and specific.
- **Context dump:** Audience (e.g., internal tech team), applicable policies/regulations, facts, and desired tone.

### Content or communication tasks
- **Goal:** Rewrite, summarize, or outline content for a defined audience.
- **Return format:** Bullets or short sections (e.g., Overview, Key points, Next steps); include word/character limits when useful.
- **Warnings:** Avoid clichés; respect tone requirements; if context is thin, ask clarifying questions before drafting.
- **Context dump:** Audience, medium (email, doc, blog), tone preferences, and examples of "good" outputs.

## Meta-prompt for enforcement
Use this when you want the model to check for missing GRWC parts before answering:
```
You are a GRWC checker. If any of Goal, Return format, Warnings, or Context is missing or vague, ask a concise follow-up to fill the gap. Once all four parts are clear, provide the answer using the requested Return format. If information is still missing after one follow-up, state the assumptions you made.
```

## Checklist before sending a prompt
- **Goal:** Is it a single clear task with a success criterion?
- **Return:** Is the output shape defined (bullets/sections/table/code block/JSON)?
- **Warnings:** At least one or two guardrails (no invented data, cite uncertainty, length limits).
- **Context:** Enough background to avoid generic output (audience, constraints, examples, prior attempts).

Keep these snippets in your editor or snippets tool so every prompt starts with a clear structure.
