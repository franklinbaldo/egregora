Feature: Avatar Command Processing
  As a system administrator or automated agent
  I want to process avatar update commands from chat messages
  So that user profiles are updated with their chosen avatar images

  Background:
    Given a configured AvatarContext

  Scenario: Successfully process a set avatar command
    Given a user "author1" has issued a command to set avatar to "http://example.com/avatar.jpg"
    When the system processes the avatar commands
    Then the avatar should be downloaded from "http://example.com/avatar.jpg"
    And the profile for "author1" should be updated with the new avatar
    And the command result for "author1" should indicate success

  Scenario: Reuse HTTP client for multiple commands
    Given a user "author1" has issued a command to set avatar to "http://example.com/url1.jpg"
    And a user "author2" has issued a command to set avatar to "http://example.com/url2.jpg"
    When the system processes the avatar commands
    Then the HTTP client should be created exactly once
    And the avatar for "author1" should be processed using the client
    And the avatar for "author2" should be processed using the client

  Scenario: Handle unset avatar command
    Given a user "author1" has issued a command to unset avatar
    When the system processes the avatar commands
    Then the profile for "author1" should have its avatar removed
    And the command result for "author1" should indicate success

  Scenario: Handle download failure gracefully
    Given a user "author1" has issued a command to set avatar to "http://example.com/broken.jpg"
    And the download for "http://example.com/broken.jpg" will fail with an error
    When the system processes the avatar commands
    Then the command result for "author1" should indicate failure
    And the profile for "author1" should NOT be updated

  Scenario: Ignore non-avatar commands
    Given a user "author1" has issued a command to set "bio" to "some text"
    When the system processes the avatar commands
    Then no avatar processing should occur for "author1"
