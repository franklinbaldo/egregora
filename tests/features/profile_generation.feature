Feature: Profile Generation
  As a system
  I want to generate author profiles from chat history
  So that I can maintain an up-to-date knowledge base about contributors

  Scenario: Profile Document Metadata Integrity
    Given a profile document is created with subject "john-uuid"
    Then the document author should be Egregora
    And the metadata should contain the subject "john-uuid"

  Scenario: Generate One Profile Per Author
    Given a chat context with configured writer model "gemini-2.0-flash"
    And a chat history with messages:
      | author_uuid | author_name | text      |
      | john-uuid   | John        | Message 1 |
      | john-uuid   | John        | Message 2 |
      | alice-uuid  | Alice       | Message 3 |
    When profile posts are generated for the window "2025-03-07"
    Then "2" profile posts should be created
    And all generated documents should be of type "PROFILE"
    And all generated documents should be authored by Egregora

  Scenario: Analyze Full Author History
    Given a chat context with configured writer model "gemini-2.0-flash"
    And a chat history with "5" messages from "John"
    When profile generation is triggered for "John"
    Then the content generator should receive "5" messages

  Scenario: LLM Decides Content
    Given a chat context with configured writer model "gemini-2.0-flash"
    And an existing profile for "John" with bio "Old Bio"
    And new messages from "John" about "AI Safety"
    When the LLM decides the profile content
    Then the prompt should contain "Old Bio"
    And the prompt should contain "AI Safety"
    And the generated content should reflect the LLM decision

  Scenario: Prompt Construction Details
    Given messages from "John":
      | text      | timestamp  |
      | Message 1 | 2025-03-01 |
      | Message 2 | 2025-03-02 |
    When the profile generation prompt is built for "John"
    Then the prompt should contain all message texts
    And the prompt should ask for analysis
    And the prompt should specify "profile" post format

  Scenario Outline: Prompt handles various interest formats
    Given messages from "Eve":
      | text      | timestamp  |
      | Hello     | 2025-03-01 |
    And an existing profile for "Eve" with interests "<Interests>"
    When the profile generation prompt is built for "Eve"
    Then the prompt should contain "<ExpectedContent>"

    Examples:
      | Interests   | ExpectedContent      |
      | None        | Interests: None      |
      | AI Safety   | Interests: AI Safety |
