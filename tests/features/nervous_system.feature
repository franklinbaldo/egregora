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

  Scenario: Error Boundary captures and routes exceptions
    Given the pipeline is configured with "DefaultErrorBoundary"
    When a "EnrichmentError" occurs during the "ENRICHMENT" phase
    Then the error should be caught by the boundary
    And a "PipelineWarning" event should be emitted
    And the pipeline should continue execution (non-fatal strategy)

  Scenario: Fatal error halts pipeline and persists state
    Given the pipeline is running
    When a "DatabaseConnectionError" occurs (fatal)
    Then the error should be caught by the boundary
    And a "PipelineError" event should be emitted
    And the pipeline state should be persisted to disk
    And the pipeline should terminate with exit code 1
