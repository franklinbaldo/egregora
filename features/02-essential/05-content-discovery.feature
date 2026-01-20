Feature: Content Discovery and Ranking
  As a user with multiple generated blog posts
  I want to automatically discover my best memories and conversations
  So that I can easily find and share the most meaningful moments

  Background:
    Given I have a blog with 30 generated posts

  Scenario: Automatic ranking with zero configuration
    Given I have never configured ranking settings
    When I transform my chat history
    Then posts should be automatically ranked in the background
    And I should not need to enable or configure ranking
    And the system should identify the best posts without my input

  Scenario: Discover best memories with simple command
    Given I have 150 blog posts from 3 years of conversations
    And I want to find the most meaningful moments
    When I run the command to show top posts
    Then I should see the 10 highest-quality posts
    And the results should feel emotionally right
    And I can easily share these with others
    And I did not need to configure anything

  Scenario: Top posts section appears automatically in site
    Given posts have been generated and ranked
    When I view my blog site
    Then a "Top Posts" or "Highlights" section should be visible
    And this feature should work without explicit enablement
    And the section should showcase the best content
    And navigation to top posts should be intuitive

  Scenario: Maya finds her family's treasures
    Given Maya has transformed her family WhatsApp group
    And the chat contains everyday chatter mixed with meaningful moments
    When she uses the discovery feature
    Then she should see highlights like "The Baby Announcement" and "Dad's Birthday Surprise"
    And mundane conversations should rank lower
    And she should think "These ARE our best memories!"
    And she can confidently share these with family members

  Scenario: Evaluate post quality
    When I run the evaluation process
    Then each post should be evaluated for quality
    And posts should receive quality scores
    And evaluation criteria should be consistent
    And the process should complete successfully

  Scenario: Rank posts by quality
    Given posts have been evaluated
    When I view the rankings
    Then posts should be ordered from best to worst
    And rankings should be clearly displayed
    And the best posts should be easily identifiable

  Scenario: Compare two posts
    Given I have two posts to compare
    When the system compares them
    Then a winner should be determined
    And reasoning for the decision should be provided
    And the comparison should be fair and consistent

  Scenario: Perform multiple pairwise comparisons
    Given I have 20 posts to evaluate
    When the system performs pairwise comparisons
    Then posts should be compared systematically
    And comparisons should build toward overall rankings
    And the number of comparisons should be efficient
    And ranking confidence should increase with more comparisons

  Scenario: Calculate ranking scores
    Given posts have been compared multiple times
    When ranking scores are calculated
    Then scores should reflect win/loss records
    And scores should be normalized for comparison
    And scores should be stable after sufficient comparisons

  Scenario: Display top-ranked posts
    Given posts have been ranked
    When I request the top 10 posts
    Then the 10 highest-ranked posts should be displayed
    And rankings should be shown alongside posts
    And I should be able to access the full content of top posts

  Scenario: View comparison history
    Given posts have been evaluated with multiple comparisons
    When I view the comparison history
    Then all pairwise comparisons should be listed
    And each comparison should show the winner and reasoning
    And I should be able to filter history by post
    And timestamps should show when comparisons occurred

  Scenario: Re-evaluate posts after changes
    Given posts have been previously ranked
    And I have regenerated some posts
    When I run evaluation again
    Then newly regenerated posts should be re-evaluated
    And previous rankings should be updated
    And ranking history should be preserved

  Scenario: Handle ties in ranking
    Given two posts receive very similar scores
    When rankings are displayed
    Then tied posts should be identified
    And the system should handle ties gracefully
    And additional comparisons may be suggested to break ties

  Scenario: Evaluate posts with different lengths
    Given the blog contains both short and long posts
    When posts are evaluated
    Then length should not unfairly bias rankings
    And quality should be assessed independent of length
    And both short and long posts can rank highly

  Scenario: Evaluate posts on multiple criteria
    Given I configure evaluation criteria including clarity, engagement, and coherence
    When posts are evaluated
    Then all criteria should be considered
    And overall scores should reflect multiple dimensions
    And individual criterion scores should be available

  Scenario: Limit evaluation to subset of posts
    Given I have 100 posts but only want to evaluate recent ones
    When I run evaluation on the last 30 days
    Then only recent posts should be evaluated
    And older posts should retain previous rankings
    And the subset should be evaluated completely

  Scenario: View evaluation feedback for specific post
    Given a post has been evaluated multiple times
    When I request feedback for that post
    Then all evaluation comments should be shown
    And both strengths and weaknesses should be identified
    And the feedback should be actionable

  Scenario: Export ranking results
    Given posts have been ranked
    When I export the rankings
    Then a file with all rankings should be created
    And the file should include scores and metadata
    And the export should be in a standard format
    And exported data should be importable elsewhere

  Scenario: Persist rankings across sessions
    Given posts have been evaluated and ranked
    When I close and reopen the project
    Then rankings should be preserved
    And I should not need to re-evaluate
    And ranking history should remain intact

  Scenario: Handle evaluation errors gracefully
    Given the evaluation process encounters an error
    When an error occurs during comparison
    Then the error should be logged
    And evaluation should continue with other comparisons
    And partial results should be available
    And the user should be notified of issues

  Scenario: Provide confidence scores for rankings
    Given posts have been ranked with varying numbers of comparisons
    When I view rankings
    Then confidence scores should be displayed
    And posts with more comparisons should have higher confidence
    And low-confidence rankings should be highlighted

  Scenario: Re-rank after adding new posts
    Given I have an existing ranking of 20 posts
    And I generate 10 new posts
    When I run evaluation with the new posts
    Then new posts should be integrated into rankings
    And existing rankings should be adjusted if needed
    And the overall ranking should remain consistent

  Scenario: Identify consistently high-quality patterns
    Given posts have been ranked over time
    When I analyze ranking patterns
    Then I should see which topics or styles rank highly
    And patterns should inform future content generation
    And insights should be actionable for improvement
