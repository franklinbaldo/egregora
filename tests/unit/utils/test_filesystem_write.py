from pathlib import Path

import pytest
import yaml

from egregora.utils.exceptions import MissingMetadataError, UniqueFilenameError
from egregora.utils.filesystem import write_markdown_post


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for testing."""
    # Create docs directory structure that authors.py expects
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    output_dir = docs_dir / "output"
    output_dir.mkdir()
    # Create .authors.yml file in docs directory
    authors_file = docs_dir / ".authors.yml"
    authors_file.write_text("author1:\n  name: Test Author\n")
    return output_dir



def test_write_markdown_post_creates_file_with_correct_content_and_frontmatter(temp_output_dir: Path):
    """Test that write_markdown_post creates a file with the correct content and frontmatter."""
    content = "This is the post content."
    metadata = {
        "title": "Test Post",
        "slug": "test-post",
        "date": "2025-01-01",
        "authors": ["author1"],
        "tags": ["testing", "refactoring"],
    }

    filepath_str = write_markdown_post(content, metadata, temp_output_dir)
    filepath = Path(filepath_str)

    assert filepath.exists()

    with filepath.open(encoding="utf-8") as f:
        file_content = f.read()

    # Split the frontmatter and the content
    parts = file_content.split("---")
    frontmatter_str = parts[1]
    post_content = parts[2].strip()

    frontmatter = yaml.safe_load(frontmatter_str)

    expected_frontmatter = {
        "title": "Test Post",
        "slug": "test-post",
        "date": "2025-01-01 00:00",
        "authors": ["author1"],
        "tags": ["testing", "refactoring"],
    }

    assert frontmatter == expected_frontmatter
    assert post_content == content


def test_write_markdown_post_handles_filename_collision(temp_output_dir: Path):
    """Test that write_markdown_post correctly handles filename collisions."""
    content = "This is the second post."
    metadata = {"title": "Another Test Post", "slug": "test-post", "date": "2025-01-01"}

    # Create the first post
    write_markdown_post(
        "First post", {"title": "First", "slug": "test-post", "date": "2025-01-01"}, temp_output_dir
    )

    # Create the second post, which should have a different filename
    filepath_str = write_markdown_post(content, metadata, temp_output_dir)
    filepath = Path(filepath_str)

    assert filepath.name == "2025-01-01-test-post-2.md"

    with filepath.open(encoding="utf-8") as f:
        file_content = f.read()

    parts = file_content.split("---")
    frontmatter = yaml.safe_load(parts[1])

    assert frontmatter["slug"] == "test-post-2"


def test_write_markdown_post_raises_error_on_missing_metadata(temp_output_dir: Path):
    """Test that write_markdown_post raises MissingMetadataError if required metadata is missing."""
    content = "This content will not be written."
    metadata = {"title": "Test Post"}  # Missing slug and date

    with pytest.raises(MissingMetadataError) as excinfo:
        write_markdown_post(content, metadata, temp_output_dir)

    assert "slug" in str(excinfo.value)
    assert "date" in str(excinfo.value)


def test_write_markdown_post_unique_filename_error(temp_output_dir: Path):
    """Verify it raises UniqueFilenameError after too many collisions."""
    content = "Content."
    metadata = {"title": "Full Post", "slug": "full-post", "date": "2023-03-03"}
    output_dir = temp_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create files to cause collisions up to the limit (default 100 attempts)
    base_filepath = output_dir / "2023-03-03-full-post.md"
    base_filepath.touch()
    for i in range(2, 102):
        filepath = output_dir / f"2023-03-03-full-post-{i}.md"
        filepath.touch()

    with pytest.raises(UniqueFilenameError) as excinfo:
        write_markdown_post(content, metadata, output_dir)

    assert "full-post" in str(excinfo.value)
    assert "100" in str(excinfo.value)
