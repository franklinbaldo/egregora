Feature: Model Key Rotation
  As a developer
  I want the system to rotate through API keys and models when failures occur
  So that the application remains resilient to rate limits and outages

  Scenario: Exhaust keys per model before switching models
    Given I have models "model-1,model-2,model-3"
    And I have API keys "key-a,key-b,key-c"
    And the first 8 API calls fail with 429 error
    When I execute the operation with rotation
    Then the call log should show 9 attempts
    And the rotation order should be correct
    And the result should be "Success with model-3 and key-c"

  Scenario: Fail when all models and keys are exhausted
    Given I have models "model-1,model-2"
    And I have API keys "key-a,key-b"
    And all API calls fail
    When I execute the operation with rotation
    Then it should raise AllModelsExhaustedError

  Scenario: Succeed on first try
    Given I have models "model-1,model-2"
    And I have API keys "key-a,key-b"
    And the API call succeeds immediately
    When I execute the operation with rotation
    Then the call log should show 1 attempt
    And the attempt should be with "model-1" and "key-a"
