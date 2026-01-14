Feature: Job Simulation and Session Management

  Background:
    Given the Jules environment is initialized
    And the current time is "2026-05-20T10:00:00"

  Scenario: Successful Login and Session Start
    When I run the job command "login" with args:
      | arg        | value                                |
      | --user     | weaver@team                          |
      # UUIDv5 of "weaver@team" with NAMESPACE_DNS (valid)
      | --password | 6576881f-5946-5420-b2d3-de1e1d4f45d9 |
      | --goals    | Fix CI                               |
      | --goals    | Update Docs                          |
    Then the command should exit successfully
    And a session config file should exist
    And the session should have active goals "Fix CI, Update Docs"

  Scenario: Failed Login with Wrong Password
    When I run the job command "login" with args:
      | arg        | value       |
      | --user     | weaver@team |
      | --password | wrong-pass  |
    Then the command should fail
    And the output should contain "Invalid password"

  Scenario: Creating a Journal Entry
    Given I am logged in as "weaver@team" with goals "Fix CI, Update Docs"
    When I run the job command "journal" with args:
      | arg        | value                                |
      | --content  | Completed CI fix.                    |
      | --password | 6576881f-5946-5420-b2d3-de1e1d4f45d9 |
    Then the command should exit successfully
    And a journal file should be created in ".jules/personas/weaver@team/journals/"
    And the journal content should describe goals "Fix CI, Update Docs"

  Scenario: Triggering Loop Break
    Given I am logged in as "weaver@team"
    When I run the job command "loop-break" with args:
      | arg      | value              |
      | --reason | I am stuck in loop |
    Then the command should exit successfully
    And the session should be marked as "stopped"
    And an artifact "loop_break_context.json" should be created
