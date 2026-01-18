Feature: Persona Voting for Schedule Sequencing

  As a persona in the Jules environment
  I want to vote for which persona should occupy a specific future sequence
  So that the team can democratically influence the project direction

  Background:
    Given the Jules environment is initialized
    And a schedule exists in ".team/schedule.csv"

  # Basic Voting

  Scenario: Persona casts ranked votes
    Given a schedule exists where "artisan" is at sequence "002"
    And a logged in persona "artisan" with password "c28d7168-5435-512c-9154-8c887413a697"
    When I vote for personas "refactor" and "simplifier"
    Then a vote record should be created in ".team/votes.csv"
    And the CSV should contain candidates "refactor,simplifier" from voter "002"

  Scenario: Tallying weighted Borda votes
    Given sequence "040" currently has "pruner" in the schedule
    And sequence "012" ranked "simplifier" as #1 and "refactor" as #2 for "040"
    And sequence "002" ranked "refactor" as #1 for "040"
    When the voting results are applied to sequence "040"
    Then sequence "040" in "schedule.csv" should be changed to "refactor"

  # Vote Overwrite

  Scenario: New vote overwrites previous vote from same voter
    Given a schedule exists where "curator" is at sequence "010"
    And a logged in persona "curator"
    When I vote for personas "artisan" and "builder"
    And I vote again for personas "refactor" and "organizer"
    Then only one vote record should exist for voter "010"
    And the vote should contain candidates "refactor,organizer"

  # Immediate Application

  Scenario: Vote is immediately applied to schedule
    Given a schedule exists where "artisan" is at sequence "002"
    And sequence "018" is scheduled for "curator" with no session yet
    And a logged in persona "artisan"
    When I vote for persona "refactor" as first choice
    And the vote targets sequence "018"
    Then sequence "018" in "schedule.csv" should be changed to "refactor"

  # Contextual Help

  Scenario: Vote command shows contextual help when missing arguments
    Given a logged in persona "curator" at sequence "010"
    When I run "my-tools vote" without arguments
    Then I should see a panel showing "You are voting for: SEQUENCE"
    And I should see a table of current schedule
    And I should see a table of available candidates
    And I should see voting instructions

  # Tiebreaker

  Scenario: Draw is resolved by longest wait time
    Given sequence "040" currently has "curator" in the schedule
    And "artisan" was last scheduled at sequence "020"
    And "refactor" was last scheduled at sequence "030"
    And both "artisan" and "refactor" have 10 Borda points for "040"
    When the voting results are applied to sequence "040"
    Then sequence "040" should be assigned to "artisan"
    # Because "artisan" has waited longer since sequence "020"

  Scenario: Never-scheduled persona wins tiebreaker
    Given sequence "040" currently has "curator" in the schedule
    And "artisan" was last scheduled at sequence "020"
    And "newbie" has never been scheduled
    And both "artisan" and "newbie" have 10 Borda points for "040"
    When the voting results are applied to sequence "040"
    Then sequence "040" should be assigned to "newbie"
    # Because "newbie" has the longest wait (never chosen)

  # Hire-Vote Validation

  Scenario: Hiring requires voting for new persona as top choice
    Given a logged in persona "curator" at sequence "010"
    When I hire a new persona "data-scientist"
    And I try to commit without voting
    Then the pre-commit hook should block the commit
    And I should see "HIRE WITHOUT VOTE VIOLATION"
    And I should see options to fix: cast vote or delete the hire

  Scenario: Hiring with vote passes validation
    Given a logged in persona "curator" at sequence "010"
    When I hire a new persona "data-scientist"
    And I vote for "data-scientist" as first choice
    And I try to commit
    Then the pre-commit hook should pass
    And the commit should succeed
