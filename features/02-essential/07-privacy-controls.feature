Feature: Privacy Controls
  As a user concerned about privacy
  I want to control how personal information is handled
  So that I can safely transform and share chat history

  Background:
    Given I have a blog project
    And I have chat history containing personal information

  Scenario: Enable author anonymization
    Given I enable anonymization in configuration
    When I transform chat history
    Then all author names should be anonymized
    And anonymized identifiers should be consistent
    And the same author should always get the same identifier
    And real names should not appear in generated content

  Scenario: Anonymize selectively by author
    Given I configure anonymization for specific authors: Alice and Bob
    When I transform chat history
    Then Alice and Bob should be anonymized
    And other authors should remain identifiable
    And selective anonymization should be respected

  Scenario: Opt out specific authors from content
    Given I configure opt-out for authors: Charlie
    When I transform chat history
    Then Charlie's messages should be excluded
    And posts should not reference Charlie
    And the conversation flow should remain coherent despite exclusions

  Scenario: Preserve anonymization across sessions
    Given authors have been anonymized
    When I close and reopen the project
    Then the same anonymization mappings should be used
    And anonymous identifiers should remain consistent
    And authors should not be re-identified

  Scenario: Generate readable anonymous identifiers
    Given anonymization is enabled
    When authors are anonymized
    Then identifiers should be human-readable
    And identifiers should be distinguishable
    And identifiers should not leak personal information

  Scenario: Anonymize media metadata
    Given images contain EXIF data with location and timestamps
    When media is processed with privacy mode
    Then sensitive metadata should be stripped
    And images should not reveal personal information
    And location data should be removed

  Scenario: Hash sensitive information
    Given messages contain phone numbers and email addresses
    When privacy mode is enabled
    When posts are generated
    Then sensitive information should be redacted or hashed
    And the content should remain readable
    And privacy should be protected

  Scenario: Control privacy at different levels
    Given I configure privacy levels: full, partial, or none
    When I transform chat history
    Then the configured privacy level should be applied
    And privacy controls should match the selected level
    And behavior should be consistent with the level

  Scenario: Anonymize while preserving relationship context
    Given anonymization is enabled
    And messages reference relationships between authors
    When posts are generated
    Then relationships should still be apparent
    And anonymous identifiers should maintain relational context
    And the narrative should remain coherent

  Scenario: Configure privacy for specific content types
    Given I enable privacy for messages but not for media
    When content is processed
    Then messages should be anonymized
    And media should retain original metadata
    And selective privacy should be applied correctly

  Scenario: Warn when publishing anonymized content
    Given content has been anonymized
    When I prepare to publish the site
    Then I should be warned that anonymization is enabled
    And I should confirm that anonymization is sufficient
    And guidance should be provided for review

  Scenario: Export privacy settings
    Given I have configured privacy settings
    When I export the configuration
    Then privacy settings should be included
    And settings should be transferable to another project
    And imported settings should work correctly

  Scenario: Apply privacy retroactively
    Given posts were generated without privacy
    When I enable privacy and regenerate
    Then existing posts should be updated
    And personal information should be removed
    And the site should reflect new privacy settings

  Scenario: Maintain privacy in author profiles
    Given author profiling is enabled with anonymization
    When profiles are generated
    Then profiles should use anonymous identifiers
    And profiles should not reveal personal information
    And analysis should still be meaningful

  Scenario: Handle partially anonymized conversations
    Given some authors are anonymized and some are not
    When posts are generated
    Then mixed anonymization should work correctly
    And it should be clear which authors are anonymous
    And the narrative should handle the mix smoothly

  Scenario: Provide privacy audit
    Given content has been generated with privacy settings
    When I run a privacy audit
    Then potential privacy issues should be identified
    And the audit should check for exposed information
    And recommendations should be provided

  Scenario: Redact specific phrases or patterns
    Given I configure redaction patterns for addresses and phone numbers
    When posts are generated
    Then matching patterns should be redacted
    And redactions should be consistent
    And the content should remain readable

  Scenario: Allow manual privacy review
    Given posts have been generated with privacy controls
    When I review posts manually
    Then I should be able to identify any remaining privacy issues
    And I should be able to edit specific instances
    And manual overrides should be respected

  Scenario: Document privacy settings in site metadata
    Given privacy mode is enabled
    When the site is generated
    Then privacy settings should be documented
    And visitors should be aware content is anonymized
    And the documentation should be clear

  Scenario: Disable privacy temporarily for testing
    Given I need to test with real names
    When I disable privacy temporarily
    Then content should use real identifiers
    And I should be warned this is for testing only
    And I should be able to re-enable privacy easily
