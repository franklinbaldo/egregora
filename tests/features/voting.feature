Feature: Persona Voting for Schedule Sequencing

  As a persona in the Jules environment
  I want to vote for which persona should occupy a specific future sequence
  So that the team can democratically influence the project direction

  Background:
    Given the Jules environment is initialized
    And a schedule exists in ".jules/schedule.csv"

  Scenario: Persona casts a valid vote
    Given a schedule exists where "artisan" is at sequence "002"
    And a logged in persona "artisan" with password "c28d7168-5435-512c-9154-8c887413a697"
    When I vote for persona "refactor"
    Then a vote record should be created in ".jules/votes.csv"
    And the vote should have voter "002" and target sequence "030"
    And the vote should count for "refactor"

  Scenario: Tallying votes updates the schedule
    Given sequence "040" currently has "pruner" in the schedule
    And sequence "012" voted for "simplifier" for sequence "040"
    And sequence "002" voted for "simplifier" for sequence "040"
    And sequence "003" voted for "maintainer" for sequence "040"
    When the voting results are applied to sequence "040"
    Then sequence "040" in "schedule.csv" should be changed to "simplifier"
