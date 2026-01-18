Feature: Persona Voting for Schedule Sequencing (Rolling Window Model)

  As a persona in the Team environment
  I want to cast ranked votes for future sequences
  So that the team can democratically influence the project direction

  Background:
    Given the Team environment is initialized
    And a schedule exists in ".team/schedule.csv"

  # Rolling Window Model
  # Votes are NOT cast for a specific sequence.
  # For any target sequence N, we tally the last N votes (roster size)
  # from the most recent voters before sequence N.

  # Basic Voting

  Scenario: Persona casts ranked votes
    Given a schedule exists where "artisan" is at sequence "002"
    And a logged in persona "artisan" with password "test-pass"
    When I vote for personas "refactor" and "simplifier"
    Then a vote record should be created in ".team/votes.csv"
    And the CSV should contain candidates "refactor,simplifier" from voter "002"

  Scenario: Tallying uses rolling window of last N votes
    Given sequence "010" is the next open sequence
    And 5 personas have voted (roster size = 5)
    And sequence "005" voted for "alice" as first choice
    And sequence "006" voted for "bob" as first choice
    And sequence "007" voted for "alice" as first choice
    And sequence "008" voted for "charlie" as first choice
    And sequence "009" voted for "alice" as first choice
    When the voting results are applied to sequence "010"
    Then sequence "010" should be assigned to "alice"
    # alice: 3 first-choice votes, bob: 1, charlie: 1

  # Vote Overwrite

  Scenario: New vote overwrites previous vote from same voter
    Given a schedule exists where "curator" is at sequence "010"
    And a logged in persona "curator"
    When I vote for personas "artisan" and "builder"
    And I vote again for personas "refactor" and "organizer"
    Then only one vote record should exist for voter "010"
    And the vote should contain candidates "refactor,organizer"

  # Immediate Application

  Scenario: Vote is immediately applied to next open sequence
    Given a schedule exists where "artisan" is at sequence "002"
    And sequence "010" is the next open sequence
    And votes from sequences 005-009 favor "refactor"
    When I cast a vote for persona "refactor" as first choice
    Then the schedule should update sequence "010" to "refactor"

  # Contextual Help

  Scenario: Vote command shows contextual help when missing arguments
    Given a logged in persona "curator" at sequence "010"
    When I run "my-tools vote" without arguments
    Then I should see the next open sequence to be filled
    And I should see a table of current schedule
    And I should see a table of available candidates
    And I should see voting instructions

  # Tiebreaker

  Scenario: Draw is resolved by longest wait time
    Given sequence "040" is the next open sequence
    And votes from the last 5 sequences result in a tie:
      | persona  | points |
      | artisan  | 10     |
      | refactor | 10     |
    And "artisan" was last scheduled at sequence "020"
    And "refactor" was last scheduled at sequence "030"
    When the voting results are applied to sequence "040"
    Then sequence "040" should be assigned to "artisan"
    # Because "artisan" has waited longer since sequence "020"

  Scenario: Never-scheduled persona wins tiebreaker
    Given sequence "040" is the next open sequence
    And votes result in a tie between "artisan" (10 pts) and "newbie" (10 pts)
    And "artisan" was last scheduled at sequence "020"
    And "newbie" has never been scheduled
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
