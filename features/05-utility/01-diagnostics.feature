Feature: Diagnostics and Health Checks
  As a user
  I want to diagnose issues with my blog project
  So that I can identify and fix problems quickly

  Background:
    Given I have a blog project

  Scenario: Run basic health check
    When I run the diagnostics command
    Then the system should check project integrity
    And configuration should be validated
    And dependencies should be verified
    And the health status should be reported

  Scenario: Validate configuration file
    Given I have a configuration file
    When diagnostics run
    Then the configuration should be parsed
    And invalid settings should be detected
    And errors should be reported with clear messages
    And suggestions for fixes should be provided

  Scenario: Check API key validity
    Given I have configured an API key
    When diagnostics validate the key
    Then the key should be tested with the provider
    And validity should be confirmed or rejected
    And the user should know if the key works

  Scenario: Verify database integrity
    Given the project has database files
    When diagnostics run
    Then database files should be checked
    And schema should be validated
    And corruption should be detected if present
    And repair options should be suggested

  Scenario: Check for missing dependencies
    Given the project requires certain libraries
    When diagnostics run
    Then all required dependencies should be verified
    And missing dependencies should be listed
    And installation instructions should be provided

  Scenario: Validate input file format
    Given I provide a chat export file
    When diagnostics analyze the file
    Then the file format should be identified
    And compatibility should be confirmed
    And issues should be flagged if present

  Scenario: Check storage space
    Given the project generates content
    When diagnostics run
    Then available disk space should be checked
    And warnings should be shown if space is low
    And the user should know storage requirements

  Scenario: Verify site structure
    Given the static site has been generated
    When diagnostics check the site
    Then the site structure should be validated
    And missing files should be detected
    And structural issues should be reported

  Scenario: Test model connectivity
    Given I have configured AI models
    When diagnostics run
    Then connectivity to model providers should be tested
    And response times should be measured
    And any connection issues should be reported

  Scenario: Check for orphaned files
    Given the project has been used for a while
    When diagnostics run
    Then orphaned or unused files should be identified
    And cleanup suggestions should be provided
    And storage optimization should be recommended

  Scenario: Validate media files
    Given the project contains media files
    When diagnostics check media
    Then file integrity should be verified
    And corrupted files should be identified
    And supported formats should be confirmed

  Scenario: Check checkpoint validity
    Given checkpoints exist
    When diagnostics run
    Then checkpoint files should be validated
    And corruption should be detected
    And resumability should be confirmed

  Scenario: Run diagnostics in verbose mode
    Given I run diagnostics with verbose flag
    When diagnostics execute
    Then detailed information should be displayed
    And all checks should be logged
    And the output should be comprehensive

  Scenario: Generate diagnostic report
    When diagnostics complete
    Then a summary report should be generated
    And the report should include all findings
    And the report should be saveable
    And the report should be shareable for support

  Scenario: Test enrichment service connectivity
    Given enrichment is enabled
    When diagnostics run
    Then enrichment services should be tested
    And URL fetching should be verified
    And any service issues should be reported

  Scenario: Verify RAG index health
    Given contextual memory is enabled
    When diagnostics check the RAG index
    Then index integrity should be verified
    And index size should be reported
    And search functionality should be tested

  Scenario: Check for version compatibility
    Given the project was created with an older version
    When diagnostics run
    Then version compatibility should be checked
    And upgrade requirements should be identified
    And migration guidance should be provided

  Scenario: Validate prompt templates
    Given custom prompt templates exist
    When diagnostics check templates
    Then template syntax should be validated
    And required variables should be verified
    And template errors should be reported

  Scenario: Check privacy configuration consistency
    Given privacy settings are enabled
    When diagnostics run
    Then privacy configuration should be validated
    And inconsistencies should be identified
    And the user should be warned of potential leaks

  Scenario: Test site build process
    When diagnostics run a test build
    Then the build should complete without errors
    And build performance should be measured
    And any build issues should be reported

  Scenario: Recommend optimization opportunities
    When diagnostics complete
    Then optimization suggestions should be provided
    And performance improvements should be recommended
    And configuration tuning should be advised
