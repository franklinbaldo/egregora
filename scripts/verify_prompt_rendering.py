#!/usr/bin/env python3
"""Test script to verify prompt rendering includes journal instructions."""

import sys
from pathlib import Path

# Add .team to path
sys.path.insert(0, str(Path.cwd() / ".team"))

from repo.scheduler import collect_journals, parse_prompt_file


def test_persona_prompt(persona_id: str):
    """Test if a persona's prompt renders with journal instructions."""
    persona_dir = Path(f".team/personas/{persona_id}")
    prompt_file = persona_dir / "prompt.md"

    if not prompt_file.exists():
        print(f"❌ {persona_id}: prompt.md not found")
        return False

    # Collect journals
    journal_entries = collect_journals(persona_dir)

    # Parse with context
    context = {
        "journal_entries": journal_entries,
        "emoji": "🔍",
        "id": persona_id,
        "owner": "test_owner",
        "repo": "test_repo",
        "open_prs": [],
    }

    parsed = parse_prompt_file(prompt_file, context)
    prompt = parsed["prompt"]

    # Check if journal instructions are in the rendered prompt
    has_journal_section = "DOCUMENT - Update Journal" in prompt
    has_journal_path = f".team/personas/{persona_id}/journals/" in prompt
    has_frontmatter_example = "YAML Frontmatter" in prompt
    has_previous_entries_section = "Previous Journal Entries" in prompt

    print(f"\n{'=' * 60}")
    print(f"Persona: {persona_id}")
    print(f"{'=' * 60}")
    print(f"  Has journals directory: {(persona_dir / 'journals').exists()}")
    print(f"  Journal entries collected: {len(journal_entries)} chars")
    print(f"  ✓ Has 'DOCUMENT - Update Journal' section: {has_journal_section}")
    print(f"  ✓ Has journal path reference: {has_journal_path}")
    print(f"  ✓ Has YAML frontmatter example: {has_frontmatter_example}")
    print(f"  ✓ Has 'Previous Journal Entries' section: {has_previous_entries_section}")

    all_checks = all(
        [has_journal_section, has_journal_path, has_frontmatter_example, has_previous_entries_section]
    )

    if all_checks:
        print("  ✅ All journal instructions present")
    else:
        print("  ❌ Missing journal instructions!")

        # Show a snippet of where journal_management should be
        if "{{ journal_management }}" in prompt:
            print("  ⚠️  WARNING: Unrendered template variable found!")
            idx = prompt.find("{{ journal_management }}")
            print(f"     Snippet: ...{prompt[max(0, idx - 50) : idx + 100]}...")

    return all_checks


if __name__ == "__main__":
    personas_to_test = [
        "docs_curator",
        "organizer",
        "pruner",
        "weaver",
        "sapper",  # Should work (has journals)
        "visionary",  # Should work (has journals)
    ]

    results = {}
    for persona_id in personas_to_test:
        results[persona_id] = test_persona_prompt(persona_id)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for persona_id, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {persona_id}")
