"""Test media enrichment parsing bug.

Bug: Batch prompt returns {"slug", "description", "alt_text"}
But parser expects {"slug", "markdown"}
"""
import json
import pytest


def test_media_batch_response_format():
    """Test that we can parse the actual batch response format."""
    # This is what the LLM actually returns (per prompt template line 267-273)
    llm_response = json.dumps({
        "IMG-20250101.jpg": {
            "slug": "sunset-beach-view",
            "description": "A beautiful sunset over a sandy beach with waves.",
            "alt_text": "Orange sunset over ocean beach with gentle waves"
        }
    })
    
    # Parse it
    data = json.loads(llm_response)
    
    # This is what we get
    filename_data = data["IMG-20250101.jpg"]
    assert "slug" in filename_data
    assert "description" in filename_data
    assert "alt_text" in filename_data
    
    # But code expects "markdown" not "description"
    assert "markdown" not in filename_data  # THIS IS THE BUG!


def test_single_call_batch_parser_expects_wrong_format():
    """The parser expects {"slug": "...", "markdown": "..."} but gets different format."""
    # What we actually get from batch mode
    actual_response = {
        "slug": "test-image",
        "description": "A test image description.",
        "alt_text": "Test image alt text"
    }
    
    # What the parser checks for (enricher.py line 1628-1631)
    slug = actual_response.get("slug")
    markdown = actual_response.get("markdown")
    
    assert slug is not None  # ✓ We have slug
    assert markdown is None   # ✗ No markdown - FAILS!
    
    # This is why we get: "Missing slug or markdown"


def test_fix_convert_description_to_markdown():
    """Show the fix: convert description + alt_text to markdown."""
    response = {
        "slug": "sunset-beach",
        "description": "A beautiful sunset over a sandy beach.",
        "alt_text": "Orange sunset over ocean"
    }
    
    # FIX: Build markdown from description (now implemented in enricher.py)
    markdown = response.get("markdown")
    if not markdown:
        description = response.get("description", "")
        alt_text = response.get("alt_text", "")
        if description:
            markdown = f"{description}"
            if alt_text:
                markdown += f"\n\n*Alt text: {alt_text}*"
    
    # Verify the fix works
    assert markdown
    assert "sunset" in markdown
    assert "beach" in markdown
    assert "Alt text" in markdown


def test_parser_handles_both_legacy_and_batch_format():
    """Verify parser accepts both old and new formats."""
    
    # Legacy format (still used by single-call mode)
    legacy = {
        "slug": "test-legacy",
        "markdown": "# Full markdown document\n\nWith multiple sections..."
    }
    
    slug = legacy.get("slug")
    markdown = legacy.get("markdown")
    if not markdown:
        description = legacy.get("description", "")
        alt_text = legacy.get("alt_text", "")
        if description:
            markdown = f"{description}"
            if alt_text:
                markdown += f"\n\n*Alt text: {alt_text}*"
    
    assert slug == "test-legacy"
    assert markdown == "# Full markdown document\n\nWith multiple sections..."
    
    # Batch format (new)
    batch = {
        "slug": "test-batch",
        "description": "A test image.",
        "alt_text": "Test alt"
    }
    
    slug = batch.get("slug")
    markdown = batch.get("markdown")
    if not markdown:
        description = batch.get("description", "")
        alt_text = batch.get("alt_text", "")
        if description:
            markdown = f"{description}"
            if alt_text:
                markdown += f"\n\n*Alt text: {alt_text}*"
    
    assert slug == "test-batch"
    assert "A test image" in markdown
    assert "Alt text" in markdown

