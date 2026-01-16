Feature: MH Mail Store
    As a user
    I want a reliable mail storage based on MH format
    So that I can manage my messages with state sequences and tags without a database

    Background:
        Given an empty MH mailbox
        And a persona "user"

    Scenario: Add message
        When I add a message from "sender@team" with subject "Hello"
        Then the message should be in "inbox"
        And the message should be in "unread"
        And the message content should match "Hello"

    Scenario: Mark as read/unread
        Given a message exists in "unread"
        When I mark the message as read
        Then the message should not be in "unread"
        When I mark the message as unread
        Then the message should be in "unread"

    Scenario: Archive and Unarchive
        Given a message exists in "inbox"
        When I archive the message
        Then the message should be in "archived"
        And the message should not be in "inbox"
        When I unarchive the message
        Then the message should be in "inbox"
        And the message should not be in "archived"

    Scenario: Trash and Restore
        Given a message exists in "inbox"
        When I trash the message
        Then the message should be in "trash"
        And the message should not be in "inbox"
        And the message should not be in "archived"
        When I restore the message
        Then the message should be in "inbox"
        And the message should not be in "trash"

    Scenario: Tags
        Given a message exists
        When I add the tag "work"
        Then the tags list should include "work"
        When I remove the tag "work"
        Then the tags list should not include "work"

    Scenario: Filesystem Compatibility
        Given a message exists
        Then no file in the mailbox directory should have ":" in its name
