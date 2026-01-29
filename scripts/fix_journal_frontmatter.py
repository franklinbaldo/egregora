import re
from pathlib import Path

PERSONAS = {
    "curator": {"name": "Curator", "emoji": "🎭"},
    "janitor": {"name": "Janitor", "emoji": "🧹"},
    "artisan": {"name": "Artisan", "emoji": "🔨"},
    "forge": {"name": "Forge", "emoji": "⚒️"},
    "docs_curator": {"name": "Docs Curator", "emoji": "📚"},
    "scribe": {"name": "Scribe", "emoji": "✍️"},
    "shepherd": {"name": "Shepherd", "emoji": "🧑‍🌾"},
    "sheriff": {"name": "Sheriff", "emoji": "🤠"},
    "refactor": {"name": "Refactor", "emoji": "🔧"},
    "pruner": {"name": "Pruner", "emoji": "🪓"},
    "weaver": {"name": "Weaver", "emoji": "🕸️"},
    "bolt": {"name": "Bolt", "emoji": "⚡"},
    "builder": {"name": "Builder", "emoji": "🏗️"},
    "palette": {"name": "Palette", "emoji": "🎨"},
    "sentinel": {"name": "Sentinel", "emoji": "🛡️"},
    "visionary": {"name": "Visionary", "emoji": "🔮"},
    "simplifier": {"name": "Simplifier", "emoji": "📉"},
    "essentialist": {"name": "Essentialist", "emoji": "🎒"},
    "organizer": {"name": "Organizer", "emoji": "🗂️"},
}


def fix_frontmatter():
    base_dir = Path(".team/personas")

    for persona_dir in base_dir.iterdir():
        if not persona_dir.is_dir():
            continue

        persona_id = persona_dir.name
        journals_dir = persona_dir / "journals"

        if not journals_dir.exists():
            continue

        meta = PERSONAS.get(persona_id, {"name": persona_id.capitalize(), "emoji": "🤖"})

        for journal_file in journals_dir.glob("*.md"):
            content = journal_file.read_text()

            if content.startswith("---"):
                print(f"Skipping {journal_file} (already has frontmatter)")
                continue

            print(f"Fixing {journal_file}...")

            # Derive date and title from filename
            # Format: YYYY-MM-DD-HHMM-Title.md or archive.md
            stem = journal_file.stem

            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", stem)
            if date_match:
                date = date_match.group(1)
                # Remove date and HHMM from title
                # stem might be 2025-12-23-2225-Moonshot_Oracle
                parts = stem.split("-")
                # parts: ['2025', '12', '23', '2225', 'Moonshot_Oracle']
                # Reconstruct title
                if len(parts) >= 4:
                    raw_title = "-".join(parts[4:]).replace("_", " ")
                    if not raw_title and len(parts) > 3:  # Handle YYYY-MM-DD-Title
                        raw_title = "-".join(parts[3:]).replace("_", " ")
                else:
                    raw_title = stem
            else:
                # Fallback for archive.md or non-standard names
                date = "2025-01-01"  # Default or today? Maybe file mod time?
                raw_title = stem.replace("_", " ").capitalize()

            # If archive.md, give it a generic title
            if stem == "archive":
                raw_title = "Historical Archive"
                # Keep date generic or try to find first date in content?
                # Let's verify content for date.
                content.strip().split("\n")[0]
                # ## 2024-05-23 - ...
                content_date_match = re.search(r"(\d{4}-\d{2}-\d{2})", content)
                if content_date_match:
                    date = content_date_match.group(1)

            title = f"{meta['emoji']} {raw_title}"

            frontmatter = f"""---
title: "{title}"
date: {date}
author: "{meta["name"]}"
emoji: "{meta["emoji"]}"
type: journal
---

"""

            new_content = frontmatter + content
            journal_file.write_text(new_content)


if __name__ == "__main__":
    fix_frontmatter()
