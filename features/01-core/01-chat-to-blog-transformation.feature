Feature: Chat-to-Blog Transformation
  As a user with chat history
  I want to transform my conversations into readable blog posts
  So that I can preserve and share meaningful discussions

  Background:
    Given I have initialized a blog project
    And I have a chat export file

  Scenario: Transform a simple conversation into a blog post
    Given the chat contains 50 messages from 3 participants
    And the messages discuss a single topic
    When I transform the chat into blog posts
    Then at least 1 blog post should be generated
    And each post should have a title
    And each post should have readable content
    And each post should have a publication date

  Scenario: Transform a multi-topic conversation
    Given the chat contains 500 messages
    And the messages discuss multiple distinct topics
    When I transform the chat into blog posts
    Then multiple blog posts should be generated
    And each post should focus on a coherent topic
    And posts should not mix unrelated discussions

  Scenario: Handle long conversations with segmentation
    Given the chat contains 10,000 messages over 6 months
    When I transform the chat with a window size of 100 messages
    Then the conversation should be split into manageable segments
    And each segment should generate its own blog post
    And segments should maintain narrative continuity

  Scenario: Transform conversation with date range filter
    Given the chat contains messages from January to December
    When I transform only messages from March to May
    Then only posts from the specified date range should be generated
    And messages outside the range should be ignored

  Scenario Outline: Transform with different window sizes
    Given the chat contains 1000 messages
    When I transform using a window size of <window_size> <unit>
    Then the messages should be grouped into windows of <window_size> <unit>
    And each window should generate a separate post
    And the number of posts should be approximately <expected_posts>

    Examples:
      | window_size | unit     | expected_posts |
      | 50          | messages | 20             |
      | 200         | messages | 5              |
      | 24          | hours    | varies         |
      | 7           | days     | varies         |

  Scenario: Transform with overlapping windows for continuity
    Given the chat contains 300 messages
    When I transform with 100-message windows and 20% overlap
    Then each window should share 20 messages with the next window
    And posts should reference context from overlapping regions
    And narrative flow should be smoother than non-overlapping windows

  Scenario: Resume transformation after interruption
    Given I started transforming a large chat export
    And the transformation was interrupted after processing 5 windows
    When I resume the transformation
    Then it should continue from window 6
    And previously generated posts should not be regenerated
    And all windows should be processed by completion

  Scenario: Force refresh all content
    Given I have previously transformed a chat export
    And blog posts already exist
    When I transform with force refresh enabled
    Then all existing posts should be regenerated
    And new posts should replace old posts
    And all content should reflect current configuration

  Scenario: Handle empty or trivial conversations
    Given the chat contains only 5 messages with greetings
    When I attempt to transform the chat
    Then the system should handle it gracefully
    And either no post is generated or a minimal post is created
    And no errors should occur

  Scenario: Preserve message metadata
    Given the chat contains messages with timestamps and authors
    When I transform the chat into blog posts
    Then posts should include or reference original message dates
    And posts should attribute content to the correct participants
    And the chronological order should be maintained

  Scenario: Transform with maximum window limit
    Given the chat contains 1000 messages
    When I transform with a maximum of 5 windows
    Then only the first 5 windows should be processed
    And transformation should stop after 5 windows
    And remaining messages should be unprocessed

  Scenario: Handle unsupported file format
    Given I have a file that is not a valid chat export
    When I attempt to transform the file
    Then the system should reject the file
    And an appropriate error message should be displayed
    And no partial content should be generated

  Scenario: Transform with timezone normalization
    Given the chat contains messages with timestamps in different timezones
    When I transform the chat with a target timezone
    Then all timestamps should be normalized to the target timezone
    And chronological order should be correct in the target timezone
    And posts should display dates in the target timezone
