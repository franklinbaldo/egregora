Feature: Persona Voting for Schedule Sequencing

  As a persona in the Jules environment
  I want to vote for which persona should occupy a specific future sequence
  So that the team can democratically influence the project direction

  Background:
    Given the Jules environment is initialized
    And a schedule exists in ".jules/schedule.csv"

  Scenario: Persona casts a valid vote
    Given a logged in persona "artisan" with password "c28d7168-5435-512c-9154-8c887413a697"
    When I vote for persona "refactor" to occupy sequence "020"
    Then a vote record should be created in ".jules/votes/020/artisan.json"
    And the vote should count for "refactor"

  Scenario: Voting on an already started sequence is blocked
    Given a logged in persona "curator"
    And sequence "001" has already been executed
    When I attempt to vote for persona "janitor" to occupy sequence "001"
    Then the system should reject the vote with an error

  Scenario: Tallying votes updates the schedule
    Given sequence "025" currently has "typeguard" in the schedule
    And "curator" voted for "simplifier" for sequence "025"
    And "artisan" voted for "simplifier" for sequence "025"
    And "bolt" voted for "maintainer" for sequence "025"
    When the voting results are applied
    Then sequence "025" in "schedule.csv" should be changed to "simplifier"
