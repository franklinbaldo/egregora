"""Behavioral tests for knowledge profiles."""

import uuid
from unittest.mock import MagicMock

from egregora.knowledge import profiles

# --- Write/Read Profile ---


def test_write_and_read_profile(tmp_path):
    """Verify writing a profile and reading it back."""
    # Given
    profiles_dir = tmp_path / "profiles"
    author_uuid = str(uuid.uuid4())
    content = "# Bio\nUser bio here."

    # When
    profiles.write_profile(author_uuid, content, profiles_dir)
    read_content = profiles.read_profile(author_uuid, profiles_dir)

    # Then
    assert "User bio here." in read_content
    assert f"uuid: {author_uuid}" in read_content
    assert (profiles_dir / author_uuid / "index.md").exists()


def test_write_profile_preserves_metadata(tmp_path):
    """Verify updating a profile preserves existing metadata."""
    # Given
    profiles_dir = tmp_path / "profiles"
    author_uuid = str(uuid.uuid4())

    # Initial write with alias
    initial_content = "---\nalias: OldAlias\n---\nOld content."
    # We cheat a bit to set initial state manually to ensure exact format
    profiles_dir.mkdir(parents=True, exist_ok=True)
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir()
    (author_dir / "index.md").write_text(initial_content, encoding="utf-8")

    # When
    profiles.write_profile(author_uuid, "New content.", profiles_dir)

    # Then
    read_content = profiles.read_profile(author_uuid, profiles_dir)
    assert "alias: OldAlias" in read_content
    assert "New content." in read_content


# --- Command Processing ---


def test_apply_alias_command(tmp_path):
    """Verify 'set alias' command updates profile."""
    # Given
    profiles_dir = tmp_path / "profiles"
    author_uuid = str(uuid.uuid4())
    command = {"command": "set", "target": "alias", "value": "NewAlias"}
    timestamp = "2023-01-01"

    # When
    profiles.apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)

    # Then
    content = profiles.read_profile(author_uuid, profiles_dir)
    # The current implementation updates the markdown body, not the frontmatter
    assert 'Alias: "NewAlias"' in content


def test_apply_invalid_alias_command(tmp_path):
    """Verify invalid alias is rejected."""
    # Given
    profiles_dir = tmp_path / "profiles"
    author_uuid = str(uuid.uuid4())
    # Create profile first
    profiles.write_profile(author_uuid, "Content", profiles_dir)

    command = {"command": "set", "target": "alias", "value": ""}  # Empty alias
    timestamp = "2023-01-01"

    # When
    profiles.apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)

    # Then
    content = profiles.read_profile(author_uuid, profiles_dir)
    assert "alias:" not in content or "alias: null" in content or "alias: " not in content
    # Check that it wasn't added if it didn't exist, or wasn't changed if it did
    # Since we created it fresh, it has no alias.


def test_apply_bio_command(tmp_path):
    """Verify 'set bio' command updates profile."""
    # Given
    profiles_dir = tmp_path / "profiles"
    author_uuid = str(uuid.uuid4())
    command = {"command": "set", "target": "bio", "value": "New Bio"}
    timestamp = "2023-01-01"

    # When
    profiles.apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)

    # Then
    content = profiles.read_profile(author_uuid, profiles_dir)
    assert '"New Bio"' in content


def test_apply_privacy_opt_out(tmp_path):
    """Verify 'opt-out' command updates profile."""
    # Given
    profiles_dir = tmp_path / "profiles"
    author_uuid = str(uuid.uuid4())
    command = {"command": "opt-out", "target": "privacy"}
    timestamp = "2023-01-01"

    # When
    profiles.apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)

    # Then
    content = profiles.read_profile(author_uuid, profiles_dir)
    assert "Status: OPTED OUT" in content
    assert profiles.is_opted_out(author_uuid, profiles_dir)


# --- Author Extraction ---


def test_extract_authors_fast_regex(tmp_path):
    """Verify fast regex extraction of authors."""
    # Given
    md_file = tmp_path / "post.md"
    content = """---
title: Post
authors:
  - author1
  - author2
---
Content
"""
    md_file.write_text(content, encoding="utf-8")

    # When
    authors = profiles.extract_authors_from_post(md_file, fast=True)

    # Then
    assert "author1" in authors
    assert "author2" in authors
    assert len(authors) == 2


def test_extract_authors_fast_single(tmp_path):
    """Verify fast regex extraction of single author."""
    # Given
    md_file = tmp_path / "post.md"
    content = """---
title: Post
authors: author1
---
Content
"""
    md_file.write_text(content, encoding="utf-8")

    # When
    authors = profiles.extract_authors_from_post(md_file, fast=True)

    # Then
    assert "author1" in authors
    assert len(authors) == 1


def test_extract_authors_slow_yaml(tmp_path):
    """Verify robust YAML extraction of authors."""
    # Given
    md_file = tmp_path / "post.md"
    # Complex yaml that might confuse regex (e.g. comments, flow style)
    content = """---
title: Post
authors: ["author1", "author2"]
---
Content
"""
    md_file.write_text(content, encoding="utf-8")

    # When
    authors = profiles.extract_authors_from_post(md_file, fast=False)

    # Then
    assert "author1" in authors
    assert "author2" in authors


# --- Active Authors ---


def test_get_active_authors_from_table():
    """Verify getting active authors from Ibis table."""
    # Given
    mock_table = MagicMock()
    # Chain: table.filter().select().distinct().execute()
    mock_query = mock_table.filter.return_value.select.return_value.distinct.return_value
    mock_query.execute.return_value = ["author1", "author2"]

    # When
    result = profiles.get_active_authors(mock_table)

    # Then
    assert "author1" in result
    assert "author2" in result
    assert "system" not in result  # Filter logic handles this but here we mock return


def test_get_active_authors_with_limit():
    """Verify getting active authors with limit."""
    # Given
    mock_table = MagicMock()
    # Chain for limit: group_by().count().rename().sort_by().limit().execute()
    mock_limit_query = mock_table.filter.return_value.group_by.return_value.count.return_value.rename.return_value.sort_by.return_value.limit.return_value

    # Mock result as dataframe-like with columns
    mock_df = MagicMock()
    mock_df.columns = ["author_uuid", "message_count"]
    mock_df.__getitem__.return_value.tolist.return_value = ["author1"]
    mock_limit_query.execute.return_value = mock_df

    # When
    result = profiles.get_active_authors(mock_table, limit=1)

    # Then
    assert result == ["author1"]
