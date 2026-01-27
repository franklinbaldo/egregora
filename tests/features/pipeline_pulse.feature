Feature: Pipeline Pulse (Real-Time Telemetry)
  As a user running a long blog generation
  I want to see real-time progress and metrics
  So that I know the system is working and how much it costs

  Scenario: Display Phase Progress
    Given the pipeline is in the "PROCESSING" phase
    And there are 10 windows total
    When window 3 is completed
    Then the progress bar should show "30%" completion
    And the current status text should display "Processing Window 4/10..."

  Scenario: Live Cost Estimation
    Given the pipeline is running
    When the "WriterAgent" consumes 1000 input tokens and 200 output tokens
    Then a "TokenUsage" event is emitted
    And the displayed "Estimated Cost" should increase by the appropriate amount
    And the displayed "Total Tokens" count should update

  Scenario: Heartbeat Indicator
    Given the pipeline is processing a large window (slow operation)
    When 5 seconds pass without a major phase change
    Then the "Pulse" indicator should animate
    So that I know the process has not hung

  Scenario: Summary Report at Completion
    Given the pipeline completes successfully
    When the process terminates
    Then a summary table should be displayed containing:
      | Metric           | Presence |
      | Total Duration   | Yes      |
      | Total Cost       | Yes      |
      | Posts Generated  | Yes      |
      | Errors/Warnings  | Yes      |
