Feature: Oracle Facilitator
  As a system orchestrator
  I want to use an Oracle persona to unblock sessions awaiting user feedback
  In order to maintain continuous progress without manual intervention

  Scenario: Unblocking a session awaiting user feedback
    Given a session for persona "refactor" is in state "AWAITING_USER_FEEDBACK"
    And the session has a pending question "How should I handle the legacy test files?"
    When the scheduler runs the facilitator tick
    Then a mail from "facilitator" should be sent to "oracle"
    And the mail subject should contain "Help requested for refactor"
    And the mail body should contain "How should I handle the legacy test files?"

  Scenario: Delivering Oracle response back to the session
    Given a session for persona "refactor" is in state "AWAITING_USER_FEEDBACK"
    And there is a mail from "oracle" to "refactor" with content "Please proceed by modularizing the legacy tests and deliver a WIP."
    When the scheduler runs the facilitator tick
    Then the message "Please proceed by modularizing the legacy tests and deliver a WIP." should be sent to the "refactor" session
    And the mail from "oracle" to "refactor" should be marked as read
