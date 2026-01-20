Feature: Static Site Output
  As a user with generated blog posts
  I want a browsable static website
  So that I can read, share, and publish my content

  Background:
    Given I have initialized a blog project
    And blog posts have been generated

  Scenario: Generate static website structure
    When I build the static site
    Then a complete website structure should be created
    And the site should have an index page
    And the site should have individual post pages
    And the site should have a navigation system

  Scenario: Browse posts chronologically
    Given the site contains 20 posts from different dates
    When I visit the site's index page
    Then posts should be listed in chronological order
    And each post should display its publication date
    And I should be able to navigate between posts

  Scenario: View individual blog post
    Given the site contains multiple posts
    When I navigate to a specific post page
    Then the post should display its full title
    And the post should display its full content
    And the post should be formatted for readability
    And media should be embedded appropriately

  Scenario: Search for content
    Given the site contains 50 posts with various topics
    When I use the site's search functionality
    Then I should be able to search by keywords
    And search results should list matching posts
    And I should be able to navigate to search results

  Scenario: View posts with embedded media
    Given a post contains 3 images and 1 video
    When I view the post page
    Then images should be displayed inline
    And videos should be playable or linked
    And media should be appropriately sized
    And the page should load efficiently

  Scenario: Navigate site structure
    Given the site has multiple sections and posts
    When I browse the site
    Then I should have access to a navigation menu
    And the menu should show site structure
    And I should be able to jump to different sections
    And the current location should be indicated

  Scenario: View site on mobile device
    Given I access the site from a mobile browser
    When I view any page
    Then the site should be responsive
    And content should be readable without zooming
    And navigation should be accessible
    And media should scale appropriately

  Scenario: Subscribe to content updates via RSS
    Given the site has been built with posts
    When I access the site's feed URL
    Then an RSS feed should be available
    And the feed should list recent posts
    And each feed item should have a title and link
    And the feed should be valid RSS/Atom format

  Scenario: View site in dark mode
    Given the site supports theme switching
    When I enable dark mode
    Then the site should display in dark colors
    And text should remain readable
    And all pages should respect the theme
    And the preference should persist across pages

  Scenario: Load site quickly with many posts
    Given the site contains 500 posts
    When I visit the index page
    Then the page should load in reasonable time
    And performance should not degrade significantly
    And large post lists should be paginated or optimized

  Scenario: View site metadata
    Given a post has been generated with metadata
    When I inspect the post's HTML page
    Then the page should include metadata tags
    And metadata should include title, description
    And metadata should support social media sharing
    And metadata should be valid for search engines

  Scenario: Browse posts by category or tag
    Given posts are organized into categories
    When I navigate to a category page
    Then I should see all posts in that category
    And categories should be clearly labeled
    And I should be able to switch between categories

  Scenario: View site offline
    Given I have downloaded or cached the static site
    When I open the site without internet connection
    Then all pages should load correctly
    And navigation should work fully
    And only external resources should fail to load

  Scenario: Export site for hosting
    Given the static site has been generated
    When I export the site files
    Then all necessary HTML, CSS, and JavaScript should be included
    And all media files should be included
    And the site should be ready for upload to a web server
    And directory structure should be deployment-ready

  Scenario: Rebuild site with updated posts
    Given the site has been previously built
    And new posts have been generated
    When I rebuild the site
    Then new posts should appear in the site
    And existing posts should remain
    And navigation should update to include new content
    And the site should be fully functional

  Scenario: Serve site locally for preview
    Given the site has been built
    When I start a local preview server
    Then I should be able to access the site in a browser
    And the site should be served at a local URL
    And changes should be previewable before deployment

  Scenario: Customize site appearance
    Given I have provided custom styling configuration
    When I build the site
    Then the site should use the custom styles
    And colors, fonts, and layout should match configuration
    And the site should remain functional with custom styles

  Scenario: Handle special characters in post titles
    Given a post has a title with special characters: "C++ & Python: A <Comparison>"
    When the site is generated
    Then the post page should be created correctly
    And the title should display correctly in HTML
    And special characters should be properly encoded
    And links to the post should work

  Scenario: Generate site with empty blog
    Given no blog posts have been generated yet
    When I build the site
    Then the site should build without errors
    And the index page should indicate no posts
    And the site structure should be ready for future posts

  Scenario: Include author information in posts
    Given posts include author metadata
    When I view a post page
    Then the author should be displayed
    And author information should be formatted clearly
    And multiple authors should be supported if applicable
