Feature: Privacy Compliance
  As a privacy-conscious user
  I want the site to load all assets locally
  So that my browsing activity is not leaked to third-party trackers

  Scenario: Verify no external requests on demo site
    Given a clean demo site is generated
    When I navigate to the home page
    Then no requests should be made to external domains
    And the "Outfit" font should be loaded locally
    And the "Inter" font should be loaded locally
