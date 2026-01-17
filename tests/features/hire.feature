Feature: Hire a New Persona
  As a persona in the Jules environment
  I want to hire a new persona to join the team
  So that we can expand our capabilities and address specific project needs

  Background:
    Given the Jules environment is initialized

  Scenario: Successfully hiring a new persona
    Given a logged in persona "artisan"
    When I hire a new persona with id "architect", name "Architect", emoji "🏛️", role "System Design", description "Expert", and mission "Architecture"
    Then a new persona directory ".jules/personas/architect" should exist
    And the prompt file ".jules/personas/architect/prompt.md.j2" should match the RGCCOV pattern
    And the prompt frontmatter for "architect" should have "hired_by" set to "artisan"
    And the persona "architect" should appear in "my-tools roster list"

  Scenario: Attempting to hire a persona that already exists
    Given a persona directory ".jules/personas/artisan" exists
    And a logged in persona "artisan"
    When I hire a new persona with id "artisan", name "Artisan", emoji "🎨", role "Redundant", description "Fail", and mission "Fail"
    Then the hire command should fail with "Persona 'artisan' already exists"
    Then the hire command should fail with "Persona 'artisan' already exists"
