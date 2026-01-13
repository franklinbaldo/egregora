Feature: Egregora Command Processing
  As a user, I want to issue commands to the system via chat messages.
  These commands should be correctly identified, parsed, and acted upon,
  while being filtered from regular conversation content.

  Scenario: Detect valid Egregora commands
    Given a message containing a valid command
    When the system checks if it is a command
    Then it should be identified as a command

  Scenario: Ignore regular messages
    Given a message that is not a command
    When the system checks if it is a command
    Then it should not be identified as a command

  Scenario: Parse avatar command
    Given a message with the avatar command "/egregora avatar set https://example.com/avatar.jpg"
    When the system parses the command
    Then the command type should be "avatar"
    And the action should be "set"
    And the URL parameter should contain "example.com/avatar.jpg"

  Scenario: Parse bio command
    Given a message with the bio command "/egregora bio I am a BDD specialist"
    When the system parses the command
    Then the command type should be "bio"
    And the bio parameter should contain "I am a BDD specialist"

  Scenario: Parse interests command
    Given a message with the interests command "/egregora interests BDD, Gherkin, testing"
    When the system parses the command
    Then the command type should be "interests"
    And the interests parameter should contain "BDD, Gherkin, testing"

  Scenario: Filter commands from message list
    Given a list of messages containing both commands and regular text
    When the system filters out the command messages
    Then the resulting list should only contain regular messages

  Scenario: Extract commands from message list
    Given a list of messages containing both commands and regular text
    When the system extracts the command messages
    Then the resulting list should only contain command messages

  Scenario: Generate announcement for avatar update
    Given a user command message for an avatar update
    When the system generates an announcement from the command
    Then an ANNOUNCEMENT document should be created
    And the document's event type should be "avatar_update"
    And the document's content should mention the user and the avatar update

  Scenario: Generate announcement for bio update
    Given a user command message for a bio update
    When the system generates an announcement from the command
    Then an ANNOUNCEMENT document should be created
    And the document's event type should be "bio_update"
    And the document's content should contain the new bio text

  Scenario: Generate announcement for interests update
    Given a user command message for an interests update
    When the system generates an announcement from the command
    Then an ANNOUNCEMENT document should be created
    And the document's event type should be "interests_update"
    And the document's content should contain the new interests
