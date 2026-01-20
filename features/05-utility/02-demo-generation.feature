Feature: Demo Generation
  As a new user or evaluator
  I want to quickly generate a demo blog
  So that I can see what Egregora can do without using my own data

  Scenario: Generate complete demo blog
    When I run the demo generation command
    Then a complete sample blog should be created
    And the blog should contain sample posts
    And the site should be immediately viewable
    And the demo should showcase key features

  Scenario: Generate demo with default settings
    When I generate a demo without custom options
    Then default configuration should be used
    And the demo should work out of the box
    And no additional setup should be required

  Scenario: Generate demo in custom directory
    Given I specify a custom directory for the demo
    When demo generation runs
    Then the demo should be created in that directory
    And the directory should contain a complete project
    And the demo should be independent

  Scenario: Include sample conversations in demo
    When a demo is generated
    Then sample chat conversations should be included
    And conversations should demonstrate various scenarios
    And the content should be realistic and diverse

  Scenario: Demonstrate enrichment features
    Given I enable enrichment in demo generation
    When the demo is created
    Then sample posts should include enriched content
    And URL previews should be demonstrated
    And media descriptions should be shown

  Scenario: Showcase different post types
    When a demo is generated
    Then regular posts should be included
    And author profiles should be demonstrated
    And announcements should be shown if applicable
    And the variety should showcase capabilities

  Scenario: Generate demo with minimal content
    Given I want a quick minimal demo
    When I generate a demo with minimal flag
    Then a smaller demo should be created
    And generation should be faster
    And the demo should still be functional

  Scenario: Generate demo with full feature showcase
    Given I want to see all features
    When I generate a full-featured demo
    Then all major features should be demonstrated
    And the demo should be comprehensive
    And examples should cover edge cases

  Scenario: Include sample media in demo
    When a demo is generated
    Then sample images should be included
    And sample videos may be included
    And media should be properly embedded
    And the demo should showcase media handling

  Scenario: Provide demo documentation
    When a demo is generated
    Then a README or guide should be included
    And the guide should explain what's demonstrated
    And next steps should be suggested
    And the demo should be self-explanatory

  Scenario: Generate demo with custom language
    Given I specify a demo language as "Spanish"
    When the demo is generated
    Then demo content should be in Spanish
    And the demo should show multilingual capabilities
    And the language setting should be applied

  Scenario: Demonstrate ranking in demo
    Given I enable ranking in demo generation
    When the demo is created
    Then sample posts should be pre-ranked
    And ranking results should be visible
    And the demo should show evaluation features

  Scenario: Generate demo quickly for evaluation
    When I generate a demo
    Then the process should complete in reasonable time
    And I should be able to preview quickly
    And the demo should be usable immediately

  Scenario: Include sample author profiles in demo
    When a demo is generated
    Then sample author profiles should be created
    And profiles should demonstrate profiling capabilities
    And profile content should be realistic

  Scenario: Demonstrate privacy features in demo
    Given I enable privacy in demo generation
    When the demo is created
    Then anonymization should be demonstrated
    And privacy features should be visible
    And the demo should show privacy controls

  Scenario: Generate demo with RAG demonstration
    Given contextual memory is enabled
    When the demo is generated
    Then posts should demonstrate contextual awareness
    And RAG functionality should be showcased
    And context retrieval should be evident

  Scenario: Regenerate demo with different settings
    Given I previously generated a demo
    When I regenerate with different settings
    Then the new demo should reflect new settings
    And the old demo should be replaced or preserved based on options

  Scenario: Export demo for sharing
    Given I have generated a demo
    When I export the demo site
    Then the demo should be portable
    And I should be able to share it with others
    And the demo should work standalone

  Scenario: Clean up demo after evaluation
    Given I no longer need the demo
    When I remove the demo
    Then all demo files should be deleted
    And no traces should remain
    And cleanup should be complete

  Scenario: Generate demo with custom sample data
    Given I provide custom sample conversations
    When the demo is generated
    Then my custom data should be used
    And the demo should be personalized
    And custom content should be processed correctly
