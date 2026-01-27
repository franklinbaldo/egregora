# RFC 028: The Egregora Nervous System

**Title:** The Egregora Nervous System (Event-Driven Architecture)
**Author:** Visionary
**Status:** Proposed
**Created:** 2026-01-26

## 1. Problem Statement

Egregora's current orchestration logic (`write.py`) is a procedural "god script" of over 1400 lines. It suffers from:
- **Opacity:** Users have no visibility into internal state.
- **Fragility:** Error handling is inconsistent; a crash usually means restarting from scratch.
- **Rigidity:** Adding new behaviors (like "notify on error" or "update UI") requires modifying the core loop.
- **Incompleteness:** State is fragmented across multiple stores, making true "resumability" difficult.

We are treating a complex, multi-agent system as a simple batch script. This limits our ability to scale, integrate, and provide a good user experience.

## 2. Proposed Solution

We propose re-architecting the core pipeline into an **Event-Driven State Machine**, dubbed the **"Egregora Nervous System"**.

### Core Concepts

1.  **The Brain (State Machine):** A central entity that tracks the pipeline's lifecycle (`INITIALIZING` -> `PARSING` -> `WINDOWING` -> `PROCESSING` -> `COMPLETED`).
2.  **The Nerves (Event Bus):** A synchronous/asynchronous event bus where components emit signals (`WindowCreated`, `TokensConsumed`, `ErrorOccurred`).
3.  **The Reflexes (Handlers):** Decoupled listeners that react to events.
    - *UI Handler:* Updates the progress bar.
    - *Cost Handler:* Aggregates token usage.
    - *Journal Handler:* Persists checkpoints.

### Architecture Transition

**Current (Procedural):**
```python
# write.py
def main():
    data = load_data()
    for window in windows:
        try:
            process(window)
        except Exception:
            log_error()
```

**Proposed (Event-Driven):**
```python
# nervous_system.py
class NervousSystem:
    def transition_to(self, phase):
        self.state = phase
        self.bus.emit(PhaseChanged(phase))

# handlers.py
@subscribe(PhaseChanged)
def update_ui(event):
    ui.set_phase(event.new_phase)
```

## 3. Value Proposition

- **Resumability:** Because state is tracked explicitly, we can serialize the "Brain" to disk. If the process crashes, we reload the Brain and resume exactly where we left off.
- **Observability:** The UI becomes just another subscriber. We can plug in a CLI UI, a Web UI, or a Log file without changing the core logic.
- **Extensibility:** Want to send a Slack notification on error? Just add a subscriber. No need to touch `write.py`.
- **Debloating:** `write.py` shrinks from 1400 lines to a high-level orchestrator that just configures the Nervous System.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Egregora Nervous System (Event-Driven State Machine)
  As a developer and system operator
  I want a unified, event-driven state machine for the pipeline
  So that execution is observable, resumable, and modular

  Scenario: Pipeline emits events for state transitions
    Given the pipeline is initialized with "StandardStateMachine"
    When the pipeline transitions from "INITIALIZING" to "PARSING"
    Then a "PipelinePhaseChanged" event should be emitted
    And the event payload should contain:
      | field     | value        |
      | old_phase | INITIALIZING |
      | new_phase | PARSING      |

  Scenario: Pipeline resumes from checkpoint
    Given a previous pipeline run failed at phase "PROCESSING_WINDOW" with window_id "5"
    And a checkpoint exists for window "5"
    When I start the pipeline with "--resume"
    Then the pipeline should skip phases "INITIALIZING" and "PARSING"
    And the pipeline should skip processing for windows "1" through "4"
    And the pipeline should resume execution at window "5"
```

## 5. Implementation Hints

- Use Python's built-in `observable` pattern or a lightweight library like `blinker` (or just simple list of callbacks for simplicity).
- Define a `State` dataclass in `src/egregora/orchestration/state.py`.
- Refactor `write.py` incrementally: start by firing events at key points, then move logic into handlers.

## 6. Risks

- **Over-engineering:** Introducing a complex event bus for a simple script might be overkill if not scoped correctly. *Mitigation:* Start with a synchronous, in-memory bus.
- **Performance Overhead:** Too many events could slow down the loop. *Mitigation:* Granularity control (don't emit event per token, emit per request).
