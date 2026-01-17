# Quick Win: Structured Persona Extraction

## 1. The Problem
To build the [Simulator](./024-the-egregora-simulator.md), we need more than just raw text history. We need a structured understanding of *who* a user is.
Currently, `egregora/agents/profile` generates human-readable markdown summaries ("Alice is interested in photography"). This is useless for an agent simulation.

## 2. The Solution
**Structured Persona Models.**
Add a pipeline step that analyzes a user's message history and extracts a machine-readable JSON profile.

**The Data Model (`PersonaModel`):**
```python
class PersonaModel(BaseModel):
    communication_style: str  # e.g., "Terse, emoji-heavy, direct"
    core_values: list[str]    # e.g., ["Code Quality", "User Experience"]
    argumentation_style: str  # e.g., "Socratic", "Devil's Advocate"
    frequent_topics: list[str]
    typical_opening_phrase: str | None
```

**The New Command:**
`egregora persona analyze <user_uuid>`

## 3. Implementation Plan (≤30 Days)
1.  **Define Model:** Create `src/egregora/agents/profile/models.py`.
2.  **Create Agent:** Implement `PersonaAgent` in `src/egregora/agents/profile/persona.py` using `pydantic-ai`.
3.  **CLI:** Add `egregora persona analyze` to output the JSON to stdout/file.
4.  **Integration:** (Future) Hook this into the main `egregora write` pipeline to auto-generate personas alongside profiles.

## 4. Value Proposition
*   **Immediate:** Developers can inspect "what the AI thinks of them." (Fun/Viral factor).
*   **Strategic:** It builds the *essential data layer* for the Simulator Moonshot.
*   **Improved RAG:** These structured keywords can boost retrieval relevance for standard queries.
