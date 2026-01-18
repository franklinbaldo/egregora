Feature: Email Polling and Delivery
  As a Team System,
  I want to poll session activities for new mail files,
  So that I can deliver messages to recipient's active sessions automatically.

  Scenario: Detecting and delivering a new email from a session pulse
    Given a session "sessions/sender-123" exists for "weaver@team"
    And an active session "sessions/recipient-456" exists for "curator@team"
    When a new activity appears in "sessions/sender-123" with a git patch:
      """
      diff --git a/.team/personas/curator@team/mail/new/msg-789 b/.team/personas/curator@team/mail/new/msg-789
      new file mode 100644
      index 0000000..e69de29
      --- /dev/null
      +++ b/.team/personas/curator@team/mail/new/msg-789
      @@ -0,0 +1,5 @@
      +From: weaver@team
      +To: curator@team
      +Subject: Task Update
      +
      +I have finished the CI fix.
      """
    And the email poller runs
    Then a message should be sent to session "sessions/recipient-456"
    And the message content should contain "Task Update"
    And the message content should contain "weaver@team"

  Scenario: Ignoring non-mail patches
    Given a session "sessions/sender-123" exists for "weaver@team"
    When a new activity appears in "sessions/sender-123" with a git patch:
      """
      diff --git a/README.md b/README.md
      index e69de29..1234567 100644
      --- a/README.md
      +++ b/README.md
      @@ -1,1 +1,2 @@
       # Project
      +Update.
      """
    And the email poller runs
    Then no messages should be sent to any sessions
