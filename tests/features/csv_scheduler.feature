Feature: CSV-Based Persona Scheduling
  As a system orchestrator
  I want personas scheduled via a CSV file
  So that I can plan ahead and track PR outcomes

  Background:
    Given the Jules scheduler is configured with CSV-based scheduling

  Scenario: Scheduler reads next persona from schedule.csv
    Given a schedule.csv with the following rows:
      | sequence | persona     | session_id | pr_number | pr_status |
      | 001      | absolutist  |            |           |           |
      | 002      | artisan     |            |           |           |
    When the scheduler runs a sequential tick
    Then a session should be created for persona "absolutist"
    And the schedule.csv should be updated with the session_id for sequence "001"

  Scenario: Scheduler skips completed sequences
    Given a schedule.csv with the following rows:
      | sequence | persona     | session_id | pr_number | pr_status |
      | 001      | absolutist  | 123456     | 100       | merged    |
      | 002      | artisan     |            |           |           |
    When the scheduler runs a sequential tick
    Then a session should be created for persona "artisan"
    And the schedule.csv should be updated with the session_id for sequence "002"

  Scenario: Scheduler waits for active PR
    Given a schedule.csv with the following rows:
      | sequence | persona     | session_id | pr_number | pr_status |
      | 001      | absolutist  | 123456     | 100       | draft     |
    When the scheduler runs a sequential tick
    Then no new session should be created
    And the scheduler should report waiting for PR

  Scenario: Scheduler auto-extends when running low
    Given a schedule.csv with only 5 empty rows remaining
    When the scheduler runs a sequential tick
    Then the schedule.csv should contain at least 55 total rows

  Scenario: Oracle session reuse within 24 hours
    Given an Oracle session was created 12 hours ago
    When the Oracle facilitator needs to start
    Then no new Oracle session should be created
    And the existing Oracle session should be reused

  Scenario: Oracle session refresh after 24 hours
    Given an Oracle session was created 25 hours ago
    When the Oracle facilitator needs to start
    Then a new Oracle session should be created
    And the old session should be marked as expired
