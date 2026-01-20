Feature: Command System
  As a chat participant
  I want to include special commands in messages
  So that I can control how the blog is generated

  Background:
    Given I have a blog project
    And command processing is enabled

  Scenario: Execute avatar command
    Given a message contains the command "/egregora avatar https://example.com/photo.jpg"
    When the chat is processed
    Then the avatar URL should be associated with the author
    And the avatar should be usable in the generated site
    And an announcement post should be created documenting the command

  Scenario: Execute bio command
    Given a message contains "/egregora bio Software developer and coffee enthusiast"
    When the chat is processed
    Then the bio should be associated with the author
    And the bio should appear in author-related content
    And the command should be logged

  Scenario: Execute multiple commands from different authors
    Given Alice sends "/egregora avatar https://alice.com/pic.jpg"
    And Bob sends "/egregora bio Loves hiking and photography"
    When the chat is processed
    Then Alice's avatar should be set
    And Bob's bio should be set
    And each command should be processed independently

  Scenario: Ignore invalid commands
    Given a message contains "/egregora invalidcommand"
    When the chat is processed
    Then the invalid command should be ignored or flagged
    And an error or warning should be logged
    And processing should continue without failure

  Scenario: Parse command with multiple parameters
    Given a command accepts multiple parameters
    When a message contains "/egregora configure theme dark mode on"
    Then the command should be parsed correctly
    And all parameters should be extracted
    And the command should execute with the provided parameters

  Scenario: Create announcement for executed commands
    Given a command is successfully executed
    When command processing completes
    Then an announcement post should be generated
    And the announcement should describe what command was executed
    And the announcement should be visible in the blog

  Scenario: List available commands
    When I request available command documentation
    Then all supported commands should be listed
    And each command should have a description
    And usage examples should be provided

  Scenario: Execute command with privacy mode
    Given anonymization is enabled
    And a message contains a command
    When the command is processed
    Then the command should respect anonymization
    And the author should remain anonymous
    And the command should still execute correctly

  Scenario: Override previous command
    Given an author previously set an avatar
    And the author sends a new avatar command
    When the new command is processed
    Then the old avatar should be replaced
    And the new avatar should be active
    And the override should be logged

  Scenario: Process commands chronologically
    Given commands are sent at different times
    When chat is processed
    Then commands should be executed in chronological order
    And later commands should override earlier ones when applicable
    And the final state should reflect the most recent commands

  Scenario: Handle malformed command syntax
    Given a message contains "/egregora avatar" without a URL
    When the command is processed
    Then the command should be rejected
    And an error message should explain the issue
    And the user should be guided on correct syntax

  Scenario: Execute command affecting multiple authors
    Given a command configures a group setting
    When the command is executed
    Then the setting should apply to all relevant authors
    And individual author settings should be updated if needed

  Scenario: Track command execution history
    Given multiple commands have been executed
    When I view command history
    Then all executed commands should be listed
    And execution timestamps should be shown
    And the effect of each command should be documented

  Scenario: Rollback command execution
    Given a command was executed incorrectly
    When I rollback the command
    Then the previous state should be restored
    And the command's effects should be undone
    And the rollback should be logged

  Scenario: Execute command only once per author
    Given a command should only be executed once
    When an author sends the command multiple times
    Then only the first execution should apply
    Or the latest execution should override previous ones
    And the behavior should be consistent with command semantics

  Scenario: Display command help inline
    Given a message contains "/egregora help avatar"
    When the command is processed
    Then help information for the avatar command should be provided
    And the help should explain usage and parameters
    And examples should be included

  Scenario: Authenticate command sender
    Given commands should only be executed by authorized authors
    When an unauthorized author sends a command
    Then the command should be rejected
    And an authorization error should be logged
    And the author should be notified if possible

  Scenario: Process commands during incremental updates
    Given new messages with commands are added to the chat
    When I run incremental processing
    Then new commands should be detected and executed
    And previously processed commands should not re-execute
    And the command state should be up to date

  Scenario: Export command configuration
    Given commands have been executed and configured settings exist
    When I export the project configuration
    Then command-configured settings should be included
    And the export should be portable
    And settings should be restorable on import

  Scenario: Filter commands from regular content
    Given a message contains both a command and regular text
    When the message is processed
    Then the command should be executed
    And the regular text should appear in posts
    And the command itself should not appear in post content
