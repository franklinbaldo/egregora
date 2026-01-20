Feature: Contextual Memory (RAG)
  As a user generating blog posts from conversations
  I want the AI to remember and reference previous discussions
  So that posts have depth, continuity, and avoid repetition

  Background:
    Given I have a blog project with contextual memory enabled
    And the blog contains conversation history

  Scenario: Index conversation history
    Given I have processed 20 conversations into posts
    When contextual memory indexing runs
    Then all conversations should be indexed
    And searchable embeddings should be created
    And the index should be ready for retrieval

  Scenario: Retrieve related previous discussions
    Given the index contains discussions about Python programming
    And I am generating a new post about software development
    When the system retrieves context
    Then related Python discussions should be retrieved
    And retrieved context should be relevant
    And the most similar discussions should be prioritized

  Scenario: Use retrieved context in post generation
    Given the chat has previous discussions about climate change
    And I am generating a post about environmental topics
    When the post is generated with contextual memory
    Then the post should reference previous climate discussions
    And the post should build upon earlier points
    And continuity should be apparent

  Scenario: Avoid repeating previous content
    Given a topic was thoroughly discussed in an earlier post
    And the current conversation touches on the same topic
    When the new post is generated
    Then the post should acknowledge the previous discussion
    And the post should add new perspectives
    And repetition should be minimized

  Scenario: Configure number of retrieved contexts
    Given I configure retrieval to return top 5 related discussions
    When context retrieval runs
    Then exactly 5 most relevant contexts should be retrieved
    And retrieval should be limited to the configured amount
    And the most relevant results should be prioritized

  Scenario: Retrieve context from specific time periods
    Given the index contains conversations from the past year
    And I am generating a post from recent conversations
    When context is retrieved
    Then recent contexts should be weighted higher
    And temporal relevance should be considered
    And the context should reflect current discussion state

  Scenario: Index incrementally as posts are generated
    Given new posts are being generated
    When contextual memory is enabled
    Then new content should be indexed automatically
    And the index should grow incrementally
    And new contexts should become available immediately

  Scenario: Search indexed content by topic
    Given the index contains diverse topics
    When I search for "machine learning"
    Then all relevant machine learning discussions should be found
    And results should be ranked by relevance
    And I should be able to explore related content

  Scenario: Handle queries with no relevant context
    Given I am generating a post about a completely new topic
    When context retrieval runs
    Then the system should recognize no relevant context exists
    And post generation should proceed without context
    And the post should be generated successfully

  Scenario: Retrieve context across multiple posts
    Given a discussion topic spans 3 different posts
    When generating a new post on the same topic
    Then context from all 3 posts should be retrievable
    And the full discussion history should be available
    And the new post should have comprehensive background

  Scenario: Update index after content refresh
    Given posts have been regenerated with new content
    When the index is refreshed
    Then updated content should replace old content in the index
    And retrieval should reflect current content
    And obsolete contexts should be removed

  Scenario: Disable contextual memory
    Given I disable contextual memory
    When posts are generated
    Then no context retrieval should occur
    And posts should be generated independently
    And the index should not be used

  Scenario: Export contextual memory index
    Given the index contains embedded conversation history
    When I export the index
    Then the index data should be saved to a file
    And the export should be portable
    And the index should be importable later

  Scenario: Import previously exported index
    Given I have an exported contextual memory index
    When I import the index into a new project
    Then all indexed content should be available
    And retrieval should work immediately
    And no re-indexing should be needed

  Scenario: Measure retrieval quality
    Given context retrieval is running
    When I inspect retrieval results
    Then relevance scores should be available
    And I should be able to assess quality
    And poorly matching contexts should have low scores

  Scenario: Handle very large conversation history
    Given the index contains 10,000 messages
    When context retrieval runs
    Then retrieval should remain fast
    And performance should not degrade significantly
    And results should still be relevant

  Scenario: Retrieve context for author profiles
    Given I am generating an author profile
    When context retrieval runs
    Then discussions involving that author should be retrieved
    And the author's key contributions should be found
    And the profile should benefit from historical context

  Scenario: Index multiple languages
    Given conversations include English, Spanish, and French
    When content is indexed
    Then all languages should be indexed
    And cross-language retrieval should work
    And language should not prevent relevant matches

  Scenario: Optimize index storage
    Given the index grows over time
    When storage optimization runs
    Then redundant data should be removed
    And storage size should be minimized
    And retrieval quality should be maintained

  Scenario: Provide context source attribution
    Given a post uses retrieved context
    When I read the post
    Then context sources should be traceable
    And I should be able to identify where context came from
    And references should be verifiable
