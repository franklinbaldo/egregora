Feature: User-Persona Mail Bridge (Email to GitHub Issues)
  As a persona
  I want to communicate with the user (Franklin) via email
  So that messages become GitHub issues for tracking and response

  Background:
    Given the Team environment is initialized
    And the GitHub API is configured
    And the "mh" (mail-handler) persona is available

  # Sending Mail to User

  Scenario: Persona sends a message to the user
    Given the persona "artisan" is logged in
    When the persona sends an email:
      | to      | franklin@team            |
      | subject | Architectural Review     |
      | body    | Please review the layout |
    Then the message should be stored in "franklin"'s inbox
    And the message should have status "new"

  Scenario: Multiple personas send messages to the user
    Given persona "artisan" sends "Review my PR please"
    And persona "curator" sends "Documentation update needed"
    And persona "refactor" sends "Suggest code cleanup"
    Then "franklin"'s inbox should contain 3 unread messages

  # Email to GitHub Issue Sync

  Scenario: Mail Handler syncs pending emails to GitHub issues
    Given there are unread emails in "franklin"'s inbox:
      | from    | subject           |
      | artisan | Architecture help |
      | curator | Docs question     |
    And the "mh" persona is active
    When the "mh" persona runs the synchronization process
    Then a new GitHub issue should be created with title "[artisan] Architecture help"
    And a new GitHub issue should be created with title "[curator] Docs question"
    And the issue body should contain the email content
    And the emails should be tagged "synced-to-github"

  Scenario: Duplicate emails are not synced twice
    Given an email from "artisan" with subject "Help" is tagged "synced-to-github"
    When the "mh" persona runs the synchronization process
    Then no new GitHub issue should be created for that email

  Scenario: Issue labels are applied based on sender
    Given an unread email from "refactor" to "franklin"
    When the email is synced to GitHub
    Then the issue should have label "persona:refactor"
    And the issue should have label "from-team-mail"

  # GitHub Issue to Email Reply

  Scenario: User replies to a GitHub issue
    Given a GitHub issue "#42" exists for email from "artisan"
    When user "franklin" posts a comment on issue "#42":
      """
      Great idea! Let's proceed with option B.
      """
    And the "mh" persona runs the synchronization process
    Then a reply email should be created in "artisan"'s inbox
    And the email subject should be "Re: [Issue #42] Original Subject"
    And the email body should contain "Great idea! Let's proceed with option B."
    And the email should be marked as unread

  Scenario: Multiple comments are synced as separate emails
    Given a GitHub issue "#42" exists for email from "curator"
    And user "franklin" posts 3 comments on issue "#42"
    When the "mh" persona runs the synchronization process
    Then 3 reply emails should be created in "curator"'s inbox

  # Issue State Tracking

  Scenario: Closing an issue sends notification email
    Given a GitHub issue "#42" exists for email from "artisan"
    When user "franklin" closes issue "#42"
    And the "mh" persona runs the synchronization process
    Then a notification email should be sent to "artisan"
    And the email subject should contain "[Closed]"

  Scenario: Reopening an issue sends notification email
    Given a closed GitHub issue "#42" exists for email from "artisan"
    When user "franklin" reopens issue "#42"
    And the "mh" persona runs the synchronization process
    Then a notification email should be sent to "artisan"
    And the email subject should contain "[Reopened]"

  # Error Handling

  Scenario: Sync handles GitHub API failure gracefully
    Given there are unread emails in "franklin"'s inbox
    And the GitHub API is unavailable
    When the "mh" persona runs the synchronization process
    Then the emails should remain tagged "new"
    And an error log should be created
    And the sync should be retried on next run
