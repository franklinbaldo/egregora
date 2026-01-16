Feature: Persona Discovery (Roster)
  As a Jules team member
  I want to list and view available personas
  So that I can understand the team capabilities

  Background:
    Given the file system is isolated

  Scenario: Listing all available personas
    Given the following personas exist:
      | id         | emoji | description                             |
      | refactor   | 🔧    | Meticulous senior developer             |
      | artisan    | 🎨    | Skilled software craftsman              |
    When I list the available personas
    Then the command should exit successfully
    And the output should contain "refactor"
    And the output should contain "🔧"
    And the output should contain "Meticulous senior developer"
    And the output should contain "artisan"
    And the output should contain "🎨"
    And the output should contain "Skilled software craftsman"

  Scenario: Viewing a specific persona prompt
    Given a persona "forge" exists with description "Senior frontend developer"
    When I view the details for persona "forge"
    Then the command should exit successfully
    And the output should contain "FORGE"
    And the output should contain "Senior frontend developer"

  Scenario: Handling missing personas
    Given no personas exist
    When I list the available personas
    Then the command should exit with an error
    And the output should contain "No personas found"

  Scenario: Attempting to view a nonexistent persona
    Given a persona "any" exists
    When I view the details for persona "ghost"
    Then the command should exit with an error
    And the output should contain "Persona 'ghost' not found"
