Feature: Pipeline Caching
  As a developer
  I want to cache intermediate results
  So that I can improve performance and reliability

  Scenario: Enrichment cache persistence
    Given a clean cache directory
    And an enrichment cache instance
    When I store an enrichment payload "Cached content" for key "http://example.com"
    And I close the cache
    And I open a new cache instance
    Then loading the key "http://example.com" should return the payload "Cached content"

  Scenario: Writer cache persistence
    Given a clean cache directory
    And a writer cache instance
    When I store a writer result for signature "test-signature-123"
    And I close the cache
    And I open a new cache instance
    Then retrieving the signature "test-signature-123" should return the result

  Scenario: RAG cache persistence
    Given a clean cache directory
    And a RAG cache instance
    When I store a RAG value for key "test-rag-key"
    And I close the cache
    And I open a new cache instance
    Then retrieving the RAG key "test-rag-key" should return the value

  Scenario: Force refresh configuration
    Given a clean cache directory
    And a cache instance with existing data
    When I initialize a cache with refresh_tiers set to "all"
    Then it should indicate refresh needed for "WRITER" tier
    When I initialize a cache with refresh_tiers set to "writer"
    Then it should indicate refresh needed for "WRITER" tier
    And it should not indicate refresh needed for "ENRICHMENT" tier
    When I initialize a cache with refresh_tiers set to "enrichment"
    Then it should indicate refresh needed for "ENRICHMENT" tier
    And it should not indicate refresh needed for "WRITER" tier

  Scenario: Handling deserialization errors
    Given a clean cache directory
    And an enrichment cache instance
    And a corrupted cache entry for key "corrupted-key"
    When I attempt to load the key "corrupted-key"
    Then a CacheDeserializationError should be raised
    And the key "corrupted-key" should be deleted from the backend

  Scenario: Handling invalid payload types
    Given a clean cache directory
    And an enrichment cache instance
    And an invalid payload stored for key "invalid-payload-key"
    When I attempt to load the key "invalid-payload-key"
    Then a CachePayloadTypeError should be raised
    And the key "invalid-payload-key" should be deleted from the backend
