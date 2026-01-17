Feature: Persona Voting for Schedule Sequencing

  As a persona in the Jules environment
  I want to vote for which persona should occupy a specific future sequence
  So that the team can democratically influence the project direction

  Background:
    Given the Jules environment is initialized
    And a schedule exists in ".jules/schedule.csv"

  Scenario: Persona casts ranked votes
    Given a schedule exists where "artisan" is at sequence "002"
    And a logged in persona "artisan" with password "c28d7168-5435-512c-9154-8c887413a697"
    When I vote for personas "refactor" and "simplifier"
    Then a vote record should be created in ".jules/votes.csv"
    And the CSV should contain a "rank 1" vote for "refactor" from "002"
    And the CSV should contain a "rank 2" vote for "simplifier" from "002"

  Scenario: Tallying weighted Borda votes
    Given sequence "040" currently has "pruner" in the schedule
    And sequence "012" ranked "simplifier" as #1 and "refactor" as #2 for "040"
    And sequence "002" ranked "refactor" as #1 for "040"
    When the voting results are applied to sequence "040"
    Then sequence "040" in "schedule.csv" should be changed to "refactor"
