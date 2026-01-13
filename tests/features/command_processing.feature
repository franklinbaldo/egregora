Feature: Command Processing
  As a user
  I want to issue commands in chat messages using the `/egregora` prefix
  So that I can update my profile and interact with the system

  Scenario: Parsing an avatar command
    When I parse the message "/egregora avatar set https://example.com/avatar.jpg"
    Then the message should be identified as a command
    And the parsed command should have type "avatar" and action "set"
    And the parsed command parameters should contain the url "https://example.com/avatar.jpg"

  Scenario: Parsing a bio command
    When I parse the message "/egregora bio I am an AI researcher"
    Then the message should be identified as a command
    And the parsed command should have type "bio"
    And the parsed command parameters should contain the bio "I am an AI researcher"

  Scenario: Parsing an interests command
    When I parse the message "/egregora interests AI, machine learning, ethics"
    Then the message should be identified as a command
    And the parsed command should have type "interests"
    And the parsed command parameters should contain the interests "AI, machine learning, ethics"

  Scenario: Ignoring regular messages
    When I check if the message "This is a regular message" is a command
    Then it should not be identified as a command

  Scenario: Case-insensitive command detection
    When I check if the message "/EGREGORA bio my new bio" is a command
    Then it should be identified as a command

  Scenario: Filtering commands from a message list
    Given a list of messages with and without commands
    When I filter the command messages from the list
    Then the resulting list should contain only non-command messages

  Scenario: Extracting commands from a message list
    Given a list of messages with and without commands
    When I extract the command messages from the list
    Then the resulting list should contain only command messages

  Scenario: Generating an announcement for an avatar update
    Given a message containing an avatar update command from "John Doe"
    When an announcement is created from the message
    Then a document of type "ANNOUNCEMENT" should be generated
    And its event type should be "avatar_update"
    And the actor should be "John Doe"
    And the document should be authored by "Egregora"

  Scenario: Generating an announcement for a bio update
    Given a message containing a bio update command
    When an announcement is created from the message
    Then a document of type "ANNOUNCEMENT" should be generated
    And its event type should be "bio_update"

  Scenario: Generating an announcement for an interests command
    Given a message containing an interests update command
    When an announcement is created from the message
    Then a document of type "ANNOUNCEMENT" should be generated
    And its event type should be "interests_update"
