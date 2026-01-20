Feature: Media Management
  As a user with chat exports containing media
  I want images, videos, and other media to be properly handled
  So that my blog posts include rich multimedia content

  Background:
    Given I have initialized a blog project
    And I have a chat export with media files

  Scenario: Extract images from chat export
    Given the chat export contains 10 image files
    When I process the export
    Then all 10 images should be extracted
    And images should be stored in the media directory
    And images should be organized systematically
    And image filenames should be unique and stable

  Scenario: Extract videos from chat export
    Given the chat export contains 3 video files
    When I process the export
    Then all 3 videos should be extracted
    And videos should be stored appropriately
    And video formats should be preserved
    And videos should be accessible to the generated site

  Scenario: Extract audio files from chat export
    Given the chat export contains voice messages
    When I process the export
    Then audio files should be extracted
    And audio should be stored in the media directory
    And audio files should be associated with relevant messages

  Scenario: Extract documents and other attachments
    Given the chat export contains PDF and document files
    When I process the export
    Then documents should be extracted
    And documents should be stored systematically
    And document references should be preserved

  Scenario: Optimize images for web display
    Given the chat export contains large, high-resolution images
    When I process the export
    Then images should be optimized for web use
    And file sizes should be reduced appropriately
    And image quality should remain acceptable
    And the optimization should be automatic

  Scenario: Maintain image aspect ratios
    Given the export contains images of various sizes and orientations
    When images are processed and embedded
    Then aspect ratios should be preserved
    And images should not appear distorted
    And images should display correctly in posts

  Scenario: Handle duplicate media files
    Given the same image appears multiple times in the chat
    When I process the export
    Then the image should be stored only once
    And all references should point to the single stored copy
    And storage should be efficient

  Scenario: Reference media in generated posts
    Given a conversation segment includes 2 images
    When a blog post is generated for that segment
    Then the post should include references to both images
    And images should be embedded at appropriate locations
    And image markup should be correct for the output format

  Scenario: Handle missing or corrupted media files
    Given the export references media files that are corrupted
    When I process the export
    Then corrupted media should be identified
    And the processing should continue for valid media
    And the user should be notified of issues
    And posts should still be generated without corrupted media

  Scenario: Support various image formats
    Given the export contains JPEG, PNG, GIF, and WebP images
    When I process the export
    Then all image formats should be handled
    And images should be converted to web-compatible formats if needed
    And image quality should be preserved

  Scenario: Support various video formats
    Given the export contains MP4, MOV, and AVI videos
    When I process the export
    Then all video formats should be processed
    And videos should be converted to web-compatible formats if needed
    And video quality should remain acceptable

  Scenario: Generate thumbnails for videos
    Given the export contains video files
    When I process the videos
    Then thumbnail images should be generated
    And thumbnails should represent video content
    And thumbnails should be usable in post previews

  Scenario: Respect media size limits
    Given I configure a maximum media file size of 10MB
    And the export contains a 25MB video
    When I process the export
    Then the video should be handled according to size policy
    And the user should be notified if media exceeds limits
    And alternative handling should be available

  Scenario: Organize media by type
    Given the export contains images, videos, and audio
    When media is extracted
    Then files should be organized by media type
    And the directory structure should be logical
    And media should be easily browsable

  Scenario: Associate media with messages
    Given a message includes an image and text
    When I process the export
    Then the image should be associated with the message
    And the association should be preserved in generated content
    And the context of the media should be clear

  Scenario: Handle media with unusual filenames
    Given media files have names with special characters
    When I process the export
    Then filenames should be sanitized for file systems
    And files should be stored without errors
    And references should use the sanitized names
    And the original context should be preserved

  Scenario: Download external media references
    Given messages include URLs to external images
    When I enable external media downloading
    Then external media should be downloaded
    And downloaded media should be stored locally
    And references should point to local copies

  Scenario: Preserve media upload timestamps
    Given media files have creation timestamps
    When media is extracted
    Then timestamps should be preserved
    And media can be sorted chronologically
    And timestamp metadata should be available

  Scenario: Handle media without extensions
    Given some media files lack file extensions
    When I process the export
    Then file types should be detected from content
    And appropriate extensions should be added
    And files should be stored correctly

  Scenario: Include media captions in posts
    Given messages include captions for shared media
    When blog posts are generated
    Then media captions should be included
    And captions should be formatted as figure captions or descriptions
    And the relationship between media and captions should be clear
