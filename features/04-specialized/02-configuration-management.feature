Feature: Configuration Management
  As a user
  I want to customize how the blog is generated
  So that the output matches my preferences and requirements

  Background:
    Given I have initialized a blog project

  Scenario: View default configuration
    When I view the configuration file
    Then all default settings should be visible
    And settings should be organized by category
    And each setting should have a description or comment
    And the configuration should be in a readable format

  Scenario: Change AI model for content generation
    Given I configure the writer model to "gpt-4"
    When I generate posts
    Then the specified model should be used
    And posts should be generated with the new model
    And the model change should be effective immediately

  Scenario: Configure custom writing instructions
    Given I add custom instructions: "Write in a professional, technical tone"
    When posts are generated
    Then the custom instructions should be followed
    And the writing style should match the instructions
    And consistency should be maintained across posts

  Scenario: Set output language
    Given I configure the language to "French"
    When posts are generated
    Then all posts should be in French
    And the language setting should affect all generated text
    And the site interface should use French where applicable

  Scenario: Configure windowing parameters
    Given I set the window size to 200 messages
    And I set the window overlap to 10%
    When I transform a chat
    Then messages should be grouped into 200-message windows
    And windows should overlap by 10%
    And the configuration should be applied correctly

  Scenario: Enable or disable specific features
    Given I disable content enrichment
    When I generate posts
    Then enrichment should not run
    And posts should be generated without enrichment
    And the feature toggle should be respected

  Scenario: Configure timezone for timestamps
    Given I set the timezone to "America/Los_Angeles"
    When posts are generated
    Then all timestamps should be in Pacific time
    And dates should display correctly in the site
    And the timezone should be consistent throughout

  Scenario: Set maximum token limit for AI context
    Given I configure the maximum prompt tokens to 200,000
    When posts are generated
    Then the AI should use up to 200,000 tokens of context
    And the limit should prevent context overflow
    And generation should work within the limit

  Scenario: Customize prompt templates
    Given I edit the writer prompt template
    When posts are generated
    Then the custom template should be used
    And template variables should be populated correctly
    And the customization should affect output

  Scenario: Configure batch processing thresholds
    Given I set the enrichment batch threshold to 20
    When enrichment runs
    Then items should be processed in batches of 20
    And the threshold should control batch size
    And efficiency should be optimized accordingly

  Scenario: Enable or disable RAG
    Given I disable contextual memory
    When posts are generated
    Then no context retrieval should occur
    And posts should be independent
    And RAG should be fully disabled

  Scenario: Configure RAG retrieval parameters
    Given I set RAG top_k to 15
    When context retrieval runs
    Then 15 related contexts should be retrieved
    And the parameter should control retrieval count
    And the configuration should be effective

  Scenario: Set privacy and anonymization options
    Given I enable author anonymization
    When I transform chat history
    Then anonymization should be applied
    And the privacy configuration should be respected
    And settings should persist

  Scenario: Configure API keys securely
    Given I need to set an API key
    When I configure the key in environment variables
    Then the key should be read correctly
    And the key should not be stored in version control
    And the system should use the key for API calls

  Scenario: Validate configuration on load
    Given I have edited the configuration file
    When the configuration is loaded
    Then invalid settings should be detected
    And validation errors should be reported clearly
    And the user should be guided to fix errors

  Scenario: Reset configuration to defaults
    Given I have customized many settings
    When I reset to defaults
    Then all settings should return to default values
    And custom changes should be cleared
    And the system should function with defaults

  Scenario: Export configuration for sharing
    Given I have a working configuration
    When I export the configuration
    Then a portable configuration file should be created
    And the file should be importable to another project
    And sensitive information should be handled appropriately

  Scenario: Import configuration from another project
    Given I have a configuration file from another project
    When I import the configuration
    Then all compatible settings should be applied
    And the project should adopt the imported configuration
    And incompatibilities should be reported

  Scenario: Override configuration via command-line
    Given I have configuration file settings
    When I run a command with CLI overrides
    Then CLI arguments should take precedence
    And overrides should apply for that execution only
    And configuration file should remain unchanged

  Scenario: Configure different models for different agents
    Given I set writer model to "gemini-2.0-flash"
    And I set reader model to "gpt-4"
    When posts are generated and evaluated
    Then the writer should use Gemini
    And the reader should use GPT-4
    And each agent should use its configured model

  Scenario: Set temperature for content generation
    Given I configure temperature to 0.9
    When posts are generated
    Then the AI should use 0.9 temperature
    And output should be more creative
    And the setting should affect generation

  Scenario: Configure logging verbosity
    Given I set logging to debug level
    When I run any operation
    Then detailed debug logs should be output
    And the verbosity should increase
    And troubleshooting should be easier

  Scenario: Define custom date format
    Given I configure a custom date format "DD/MM/YYYY"
    When dates are displayed in the site
    Then the custom format should be used
    And dates should be consistent throughout
    And the format should be applied correctly

  Scenario: Lock configuration to prevent changes
    Given I lock the configuration
    When I attempt to modify settings
    Then changes should be prevented or warned
    And the locked state should protect configuration
    And intentional changes should require unlocking

  Scenario: Configure multiple output directories
    Given I specify different output paths for posts and media
    When content is generated
    Then posts should go to the posts directory
    And media should go to the media directory
    And the structure should match configuration

  Scenario: Migrate configuration between versions
    Given I have a configuration from an older version
    When I load it in a newer version
    Then the configuration should be migrated automatically
    And deprecated settings should be updated
    And compatibility should be maintained
