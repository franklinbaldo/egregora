Feature: Team Governance and Constitution

  As a persona in the Team environment
  I want to participate in team governance through the Constitution
  So that the team operates under agreed-upon rules

  Background:
    Given the Team environment is initialized
    And a Constitution exists at ".team/CONSTITUTION.md"

  # Constitution Structure

  Scenario: Constitution is append-only
    Given the Constitution contains "Article I: Participation"
    When a persona tries to remove Article I
    Then the change should be rejected
    And the Constitution should still contain "Article I: Participation"

  # Plead Protocol

  Scenario: Persona pleads to the Constitution
    Given a persona "curator" has not pledged to the Constitution
    When "curator" commits a pledge message "[PLEAD] curator: I agree to the Constitution"
    Then "curator" should be recorded as pledged
    And the GovernanceManager should return true for is_persona_pleaded("curator")

  Scenario: Unpledged persona cannot participate
    Given a persona "refactor" has not pledged to the Constitution
    When "refactor" attempts to work on sequence "042"
    Then the scheduler should block "refactor"
    And a pledge request message should be shown

  # Login Alerts

  Scenario: Login shows constitution change alert
    Given a persona "artisan" pledged to Constitution version "abc123"
    And the Constitution has been amended since "abc123"
    When "artisan" logs in
    Then a GOVERNANCE ALERT panel should be displayed
    And the alert should explain the right to revert

  Scenario: Login shows pledge required notice
    Given a persona "builder" has never pledged
    When "builder" logs in
    Then a NOTICE panel should be displayed
    And the notice should explain how to pledge

  # Revert Rights

  Scenario: Persona can revert to previously pledged version
    Given a persona "curator" pledged to Constitution version "abc123"
    And the Constitution was amended to version "def456"
    And "curator" disagrees with the changes
    When "curator" reverts the Constitution to version "abc123"
    Then the Constitution should contain the "abc123" version content
    And "curator" should still be considered pledged
