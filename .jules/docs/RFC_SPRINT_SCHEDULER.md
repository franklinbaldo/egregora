# Jules Scheduler RFC: Sprint & Meeting Simulation

**Date:** 2025-01-01
**Status:** Proposal

## Concept: First-Class Sprints

We propose creating a `Sprint` concept within the Jules Scheduler to formalize the sprint lifecycle.

### 1. The PO Role
The Product Owner (PO) defines the sprint structure:
- **Duration:** How many sessions (steps) the sprint requires.
- **Sequence:** An ordered list of sessions (activations of specific personas).

### 2. Session Sequence
A Sprint is a sequence of Sessions.
- **Session 1 (Start):** Simulated "Sprint Planning Meeting".
- **Sessions 2...N-1:** Execution work (Persona Activations).
- **Session N (End):** Simulated "Sprint Review/Retrospective Meeting".

### 3. Simulated Meetings
The "Meeting" sessions are special:
- **Participants:** All (or selected) personas.
- **Mechanism:**
  - Jules impersonates personas sequentially or dynamically.
  - The prompt explicitly asks for "one persona talking per step".
  - **Artifact:** A single `.jules/sprints/sprint-X/MEETING_LOG.md` (or similar) is produced to document the discussion.
- **Goal:**
  - Start: Align on goals, assign tasks.
  - End: Demo work, discuss blockers, update velocity.

## Implementation Steps (Future)
1.  Define a `Sprint` class in the scheduler configuration (`schedules.toml` or similar).
2.  Implement a "Meeting Mode" where the context switches between personas within a single session/loop.
3.  Update persona prompts to handle "Meeting Participation" context.
