Feature: Jules System Mail Interface

  Background:
    Given the mail backend is set to "local"
    And the file system is isolated

  Scenario: Sending a mail message
    When I run the mail command "send" with args:
      | arg      | value              |
      | --from   | weaver@team        |
      | --to     | curator@team       |
      | --subject| Updates            |
      | --body   | Progress is good   |
    Then the command should exit successfully
    And a mail file should exist in ".jules/personas/curator@team/mail/new"

  Scenario: Sending a broadcast message
    Given personas "alice", "bob" exist
    When I run the mail command "send" with args:
      | arg      | value              |
      | --from   | boss@team          |
      | --to     | all@team           |
      | --subject| Announcement       |
      | --body   | Everyone listen up |
    Then the command should exit successfully
    And a mail file should exist in ".jules/personas/alice/mail/new"
    And a mail file should exist in ".jules/personas/bob/mail/new"

  Scenario: Checking inbox
    Given a message exists from "boss@team" to "worker@team" with subject "Work"
    When I run the mail command "inbox" with args:
      | arg      | value       |
      | --persona| worker@team |
    Then the command should exit successfully
    And the output should contain "Work"
    And the output should contain "boss@team"
    And the output should contain "[NEW]"

  Scenario: Reading a message
    Given a message exists from "friend@team" to "me@team" with body "Secret Code: 1234"
    When I run the mail command "read" with the message key
    Then the command should exit successfully
    And the output should contain "Secret Code: 1234"
    And the message should be marked as read
