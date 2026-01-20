Feature: Resume and Checkpoint
  As a user processing large chat exports
  I want to resume interrupted operations
  So that I don't lose progress when processing is interrupted

  Background:
    Given I have a blog project
    And I have a large chat export with 10,000 messages

  Scenario: Save checkpoint during processing
    Given I am transforming the chat export
    When processing has completed 50% of windows
    Then a checkpoint should be saved automatically
    And the checkpoint should record progress
    And the checkpoint should be retrievable

  Scenario: Resume after interruption
    Given processing was interrupted after 30% completion
    When I resume the transformation
    Then processing should continue from the last checkpoint
    And completed windows should not be reprocessed
    And the remaining windows should be processed
    And the final result should be complete

  Scenario: Resume with resume flag
    Given I previously started transformation
    And the process did not complete
    When I run the command with the resume flag
    Then the system should detect the checkpoint
    And processing should resume from where it stopped
    And I should not need to manually specify the checkpoint

  Scenario: Skip completed windows on resume
    Given windows 1-10 were processed before interruption
    When I resume processing
    Then windows 1-10 should be skipped
    And processing should start at window 11
    And efficiency should be improved by skipping

  Scenario: Update checkpoint incrementally
    Given processing is running
    When each window completes
    Then the checkpoint should be updated
    And progress should be continuously saved
    And interruptions should lose minimal work

  Scenario: Resume with changed configuration
    Given processing was checkpointed
    And I modify the configuration
    When I attempt to resume
    Then I should be warned about configuration changes
    And I should choose to resume with new config or restart
    And the system should handle the decision correctly

  Scenario: Clear checkpoints after successful completion
    Given processing completes successfully
    When I view checkpoint data
    Then completed checkpoints should be cleaned up
    And storage should be freed
    And stale checkpoints should not remain

  Scenario: Manually delete checkpoint to restart
    Given a checkpoint exists
    When I delete the checkpoint manually
    And I run transformation
    Then processing should start from the beginning
    And all windows should be processed fresh
    And no resume should occur

  Scenario: Handle corrupted checkpoint
    Given a checkpoint file is corrupted
    When I attempt to resume
    Then the corruption should be detected
    And I should be warned
    And I should have the option to restart or repair
    And processing should not fail catastrophically

  Scenario: Resume with different input file
    Given I checkpointed processing of file A
    When I attempt to resume with file B
    Then the system should detect the mismatch
    And I should be warned that files differ
    And I should choose to restart or cancel

  Scenario: Display resume progress accurately
    Given I am resuming from 40% completion
    When processing continues
    Then progress should start at 40%
    And remaining progress should be accurate
    And the user should see correct completion estimates

  Scenario: Checkpoint enrichment progress
    Given enrichment is running on 500 items
    And 200 items have been enriched
    When enrichment is interrupted
    Then enrichment checkpoint should be saved
    And resuming should continue from item 201
    And completed enrichments should not be redone

  Scenario: Checkpoint evaluation progress
    Given post evaluation is running
    And 50 comparisons have been completed
    When evaluation is interrupted
    Then the checkpoint should save comparison state
    And resuming should continue with remaining comparisons
    And rankings should be updated correctly

  Scenario: Force restart ignoring checkpoints
    Given checkpoints exist
    When I run transformation with force restart flag
    Then all checkpoints should be ignored
    And processing should start from scratch
    And all content should be regenerated

  Scenario: Resume multiple parallel operations
    Given content generation and enrichment are both checkpointed
    When I resume processing
    Then both operations should resume from their checkpoints
    And each should continue independently
    And overall progress should be coordinated

  Scenario: Checkpoint with windowing changes
    Given I checkpointed with 100-message windows
    And I change to 200-message windows
    When I attempt to resume
    Then the system should detect the windowing change
    And I should be advised to restart
    And the checkpoint should be invalidated

  Scenario: Store checkpoint metadata
    Given a checkpoint is created
    When I inspect the checkpoint
    Then metadata should include timestamp
    And metadata should include configuration snapshot
    And metadata should include completion percentage
    And the checkpoint should be self-describing

  Scenario: Resume after system failure
    Given the system crashed during processing
    When I restart and resume
    Then the last good checkpoint should be found
    And processing should recover gracefully
    And no manual intervention should be needed

  Scenario: Warn before overwriting checkpoint
    Given a valid checkpoint exists
    When I start new processing without resume flag
    Then I should be warned about overwriting
    And I should confirm the action
    And accidental restarts should be prevented

  Scenario: Resume with partial window completion
    Given processing was interrupted mid-window
    When I resume
    Then the partial window should be reprocessed
    And completion should be ensured
    And no incomplete content should remain
