Feature: Reader Agent Post Evaluation and ELO Ranking

  As an AI-powered content quality evaluator
  I want to compare blog posts pairwise using structured criteria
  So that posts can be ranked by quality using ELO ratings

  Background:
    Given the reader agent is configured
    And an ELO rating database exists

  # Basic Post Comparison

  Scenario: Compare two posts and determine a winner
    Given a post "post-a" with content about Python best practices
    And a post "post-b" with content about TypeScript tips
    When the reader agent compares the two posts
    Then a comparison result should be generated
    And the result should include a winner ("a", "b", or "tie")
    And the result should include reasoning for the decision
    And feedback should be provided for both posts

  Scenario: Post comparison generates structured feedback
    Given a post "engaging-post" with high-quality content
    And a post "basic-post" with minimal content
    When the reader agent evaluates both posts
    Then "engaging-post" should receive feedback with:
      | field            | value  |
      | star_rating      | 4-5    |
      | engagement_level | high   |
    And "basic-post" should receive feedback with:
      | field            | value  |
      | star_rating      | 1-2    |
      | engagement_level | low    |

  # ELO Rating Updates

  Scenario: New posts start with default ELO rating
    Given a new post "first-post" has never been evaluated
    When I check the ELO rating for "first-post"
    Then the rating should be 1500.0
    And the comparison count should be 0

  Scenario: Winner gains rating points after comparison
    Given post "alpha" has an ELO rating of 1500
    And post "beta" has an ELO rating of 1500
    When "alpha" wins a comparison against "beta"
    Then "alpha" rating should increase
    And "beta" rating should decrease
    And the sum of rating changes should equal zero

  Scenario: Tie results in no rating change when ratings are equal
    Given post "post-x" has an ELO rating of 1550
    And post "post-y" has an ELO rating of 1550
    When the comparison results in a tie
    Then "post-x" rating should remain 1550.0
    And "post-y" rating should remain 1550.0

  # Database Persistence

  Scenario: Comparison results are persisted to database
    Given post "doc-a" and post "doc-b" exist
    When the reader agent compares them
    Then a comparison record should be created in the database
    And the record should include:
      | field               | present |
      | comparison_id       | yes     |
      | post_a_slug         | yes     |
      | post_b_slug         | yes     |
      | winner              | yes     |
      | rating_a_before     | yes     |
      | rating_a_after      | yes     |
      | rating_b_before     | yes     |
      | rating_b_after      | yes     |
      | reader_feedback     | yes     |
      | timestamp           | yes     |

  Scenario: ELO ratings table stores post statistics
    # Given post "stats-post" has been compared 5 times
    Given "stats-post" has won 3 times, lost 1 time, and tied 1 time
    When I query the elo_ratings table for "stats-post"
    Then the record should show:
      | field       | value |
      | comparisons | 5     |
      | wins        | 3     |
      | losses      | 1     |
      | ties        | 1     |

  Scenario: Comparison history can be retrieved for a post
    Given post "popular" has been compared against multiple posts
    When I request the comparison history for "popular"
    Then I should receive a list of all comparisons involving "popular"
    And each comparison should include opponent slug and outcome

  # Ranking Generation

  Scenario: Generate rankings from ELO ratings
    Given multiple posts with different ELO ratings:
      | slug      | rating |
      | excellent | 1700   |
      | good      | 1600   |
      | average   | 1500   |
      | poor      | 1400   |
    When I generate rankings
    Then the posts should be ranked in order:
      | rank | slug      |
      | 1    | excellent |
      | 2    | good      |
      | 3    | average   |
      | 4    | poor      |

  Scenario: Rankings include win rate calculation
    Given post "winner" has 8 wins, 2 losses, 0 ties
    When I generate rankings
    Then "winner" should have a win_rate of 0.8

  Scenario: Top N posts can be retrieved
    Given 10 posts with varying ELO ratings
    When I request the top 3 posts
    Then I should receive exactly 3 posts
    And they should be the 3 highest-rated posts

  # Post Selection and Pairing

  Scenario: Posts are paired for balanced comparisons
    Given 4 posts with default ratings
    And comparisons_per_post is set to 3
    When I select post pairs for evaluation
    Then each post should be scheduled for exactly 3 comparisons
    And no post should be paired with itself

  Scenario: Post pairing avoids recent duplicates
    Given post "alpha" was recently compared against "beta"
    When selecting new pairs for "alpha"
    Then "alpha" should be paired with different opponents
    And "beta" should not be selected again for "alpha"

  # CLI Integration

  Scenario: Run reader evaluation via CLI
    Given a site with 5 blog posts in the posts directory
    When I run "egregora read <site_root>"
    Then the reader should discover all 5 posts
    And comparisons should be performed
    And ELO ratings should be updated
    And rankings should be displayed in a table

  Scenario: CLI shows ranking with statistics
    Given posts have been evaluated
    When I run "egregora read <site_root>"
    Then the output should display a table with columns:
      | column       |
      | Rank         |
      | Post         |
      | ELO Rating   |
      | Comparisons  |
      | Win Rate     |

  Scenario: CLI respects model configuration
    Given the reader is configured to use "gemini-2.0-flash-exp"
    When I run "egregora read <site_root> --model gemini-2.0-flash-exp"
    Then comparisons should use the specified model
    And the model should be passed to the Pydantic AI agent

  # Edge Cases

  Scenario: Handle evaluation with only one post
    Given only one post "lonely-post" exists
    When I attempt to run reader evaluation
    Then no comparisons should be performed
    And "lonely-post" should retain its default rating of 1500

  Scenario: Handle empty posts directory
    Given the posts directory is empty
    When I run reader evaluation
    Then no posts should be discovered
    And no comparisons should be performed
    And an appropriate message should be displayed

  Scenario: Handle identical post content
    Given post "original" and post "duplicate" have identical content
    When the reader agent compares them
    Then the comparison should complete successfully
    And the result should likely be a tie
    And feedback should note the similarity

  # Feedback Quality Criteria

  Scenario: Reader evaluates posts on multiple criteria
    Given the reader agent system prompt includes quality criteria
    When comparing two posts
    Then the evaluation should consider:
      | criterion    |
      | Clarity      |
      | Engagement   |
      | Insight      |
      | Structure    |
      | Authenticity |

  Scenario: Feedback includes written commentary
    Given two posts are compared
    When the comparison completes
    Then each post should receive a comment
    And the comment should explain the rating
    And the comment should reference specific qualities

  # Configuration

  Scenario: Reader can be disabled via configuration
    Given the reader is configured with enabled: false
    When I attempt to run reader evaluation
    Then the evaluation should be skipped
    And a message should indicate the reader is disabled

  Scenario: Comparisons per post can be configured
    Given the reader is configured with comparisons_per_post: 4
    And 5 posts exist
    When I select post pairs
    Then each post should be scheduled for exactly 4 comparisons

  Scenario: Database path can be configured
    Given the reader is configured with database_path: "custom/reader.duckdb"
    When reader evaluation runs
    Then the database should be created at "custom/reader.duckdb"
    And ratings should be persisted to the custom path
