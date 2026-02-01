Feature: Content Enrichment
  As a content curator
  I want to enrich URLs and media files efficiently
  So that I can generate summaries and descriptions with minimal API overhead

  Scenario: URL enrichment uses batch_all strategy
    Given the enrichment strategy is "batch_all"
    And there are 5 pending URL enrichment tasks
    When the enrichment worker processes the batch
    Then the worker should make exactly 1 API call
    And the batch API call should contain 5 items

  Scenario: URL enrichment uses individual strategy
    Given the enrichment strategy is "individual"
    And there are 5 pending URL enrichment tasks
    When the enrichment worker processes the batch
    Then the worker should make 5 API calls

  Scenario: Media staging fails when filename is missing
    Given an enrichment task with no filename in payload
    When the worker attempts to stage the file
    Then a MediaStagingError should be raised matching "No filename in task payload"

  Scenario: Media staging fails when input zip is missing
    Given the input zip file does not exist
    And an enrichment task for file "test.jpg"
    When the worker attempts to stage the file
    Then a MediaStagingError should be raised matching "Input path not available"

  Scenario: Media staging fails when file is not in zip
    Given a valid input zip file
    And an enrichment task for file "missing.jpg" which is not in the zip
    When the worker attempts to stage the file
    Then a MediaStagingError should be raised matching "not found in ZIP"
