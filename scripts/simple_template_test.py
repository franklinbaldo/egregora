#!/usr/bin/env python3
"""Simple test to verify jinja2 template rendering."""

import jinja2

JOURNAL_MANAGEMENT = """
### 📝 DOCUMENT - Update Journal
- Create a NEW file in `.team/personas/{{ id }}/journals/`
- Naming convention: `YYYY-MM-DD-HHMM-Any_Title_You_Want.md`

## Previous Journal Entries

Below are the aggregated entries from previous sessions.

{{ journal_entries }}
"""


def test_rendering():
    env = jinja2.Environment()

    # Test 1: With journal entries
    context = {
        "id": "docs_curator",
        "journal_entries": "Previous entry 1\nPrevious entry 2",
    }

    rendered = env.from_string(JOURNAL_MANAGEMENT).render(**context)
    print("=" * 60)
    print("Test 1: With journal entries")
    print("=" * 60)
    print(rendered)
    print()

    # Test 2: Without journal entries (empty string)
    context2 = {
        "id": "docs_curator",
        "journal_entries": "",
    }

    rendered2 = env.from_string(JOURNAL_MANAGEMENT).render(**context2)
    print("=" * 60)
    print("Test 2: Without journal entries (empty)")
    print("=" * 60)
    print(rendered2)
    print()

    # Test 3: Check if {{ journal_management }} gets rendered in a prompt
    prompt_template = """
Your task is to do X.

{{ journal_management }}

Good luck!
"""

    full_context = {
        "id": "docs_curator",
        "journal_entries": "Some previous entries",
    }

    full_context["journal_management"] = env.from_string(JOURNAL_MANAGEMENT).render(**full_context)

    final_prompt = env.from_string(prompt_template).render(**full_context)
    print("=" * 60)
    print("Test 3: Full prompt rendering")
    print("=" * 60)
    print(final_prompt)

    # Check if the instructions are present
    has_instructions = "📝 DOCUMENT - Update Journal" in final_prompt
    has_path = ".team/personas/docs_curator/journals/" in final_prompt
    has_entries = "Some previous entries" in final_prompt

    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)
    print(f"Has journal instructions: {has_instructions}")
    print(f"Has correct path: {has_path}")
    print(f"Has previous entries: {has_entries}")

    if has_instructions and has_path:
        print("\n✅ Template rendering works correctly!")
    else:
        print("\n❌ Template rendering has issues!")


if __name__ == "__main__":
    test_rendering()
