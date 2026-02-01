Feature: Windowing Strategies
  As a data engineer
  I want to split message streams into windows
  So that I can process them in manageable chunks while respecting context boundaries

  Scenario Outline: Window by message count
    Given a message stream with <num_messages> messages
    When I split the stream by message count with size <step_size> and overlap <overlap_ratio>
    Then I should get <num_windows> windows
    And the window sizes should be <expected_sizes>

    Examples:
      | num_messages | step_size | overlap_ratio | num_windows | expected_sizes |
      | 100          | 50        | 0.0           | 2           | 50, 50         |
      | 120          | 50        | 0.0           | 3           | 50, 50, 20     |
      | 30           | 50        | 0.0           | 1           | 30             |
      | 0            | 50        | 0.0           | 0           |                |
      | 100          | 50        | 0.2           | 2           | 60, 50         |
      | 120          | 50        | 0.2           | 3           | 60, 60, 20     |
      | 30           | 50        | 0.2           | 1           | 30             |

  Scenario: Window by time duration
    Given a message stream spanning 300 minutes with 300 messages
    When I split the stream by time with size 2 hours and overlap 0.0
    Then I should get 3 windows
    And the window sizes should be 120, 120, 60

  Scenario: Window by byte size with simple text
    Given a message stream with 100 messages averaging 10 bytes each
    When I split the stream by bytes with limit 100 and overlap 0.0
    Then I should get more than 5 windows
    And all windows should have content

  Scenario: Window by byte size with specific messages
    Given a message stream with varying message lengths
    When I split the stream by bytes with limit 20 and overlap 0.0
    Then I should get 2 windows
    And the window sizes should be 2, 3

  Scenario: Window by byte size with overlap
    Given a message stream with varying message lengths
    When I split the stream by bytes with limit 30 and overlap 0.5
    Then I should get 3 windows
    And the window sizes should be 3, 2, 1

  Scenario: Window by bytes with duplicates
    Given a message stream with 5 messages where the first 3 share a timestamp
    When I split the stream by bytes with limit 2 and overlap 0.0
    Then I should get 2 windows
    And the first window should contain "a, b, c"
    And the second window should contain "d, e"

  Scenario: Split window into parts
    Given a single window with 100 messages
    When I split the window into 2 parts
    Then I should get 2 sub-windows
    And each sub-window should have approximately 50 messages

  Scenario: Invalid configuration
    Given a message stream with 10 messages
    When I try to split with invalid unit "invalid"
    Then an InvalidStepUnitError should be raised with unit "invalid"

  Scenario: Invalid split request
    Given a single window with 100 messages
    When I try to split the window into 1 part
    Then an InvalidSplitError should be raised with n=1

  Scenario: Max window time constraint
    Given a message stream spanning 72 hours with 72 messages
    When I split the stream by "days" with size 2 but max window time 24 hours
    Then I should get 3 windows
    And each window should span at most 24 hours

  Scenario: Window signature generation
    Given a message stream with 10 messages
    And a valid configuration with writer instructions
    When I generate a signature for the window with template "prompt template"
    And I generate another signature with the same parameters
    Then the signatures should be identical
    But if I change the template to "different template" the signature should change
