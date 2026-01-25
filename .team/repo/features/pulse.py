import csv
from pathlib import Path
from typing import Any

from repo.features.mail import list_inbox

SCHEDULE_FILE = Path(".team/schedule.csv")
LOG_FILE = Path(".team/tools_use.csv")  # Legacy
LOGS_DIR = Path(".team/logs/tools_use")  # New per-session logs

class PulseManager:
    def get_sitrep(self, persona_id: str, current_sequence: str | None) -> dict[str, Any]:
        """
        Gathers all data for a persona's situation report.
        """
        return {
            "persona": persona_id,
            "sequence": current_sequence or "unknown",
            "next_persona": self._get_next_persona(current_sequence),
            "unread_mail_count": self._get_unread_mail_count(persona_id),
            "last_tool_used": self._get_last_tool_used(persona_id),
        }

    def _get_next_persona(self, current_sequence: str | None) -> str:
        if not current_sequence or not SCHEDULE_FILE.exists():
            return "unknown"
        
        try:
            with open(SCHEDULE_FILE, mode='r', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                for i, row in enumerate(rows):
                    if row['sequence'] == current_sequence:
                        if i + 1 < len(rows):
                            next_row = rows[i+1]
                            return f"{next_row['sequence']} ({next_row['persona']})"
        except Exception:
            pass
        return "none scheduled"

    def _get_unread_mail_count(self, persona_id: str) -> int:
        try:
            # We use the existing mail feature logic
            messages = list_inbox(persona_id, unread_only=True)
            return len(messages)
        except Exception:
            return 0

    def _get_last_tool_used(self, persona_id: str) -> str:
        """
        Get the last tool used by a persona, scanning per-session log files.

        Checks both new per-session logs (.team/logs/tools_use/{persona}_*.csv)
        and legacy single log file (.team/tools_use.csv).
        """
        all_rows = []

        # Read from new per-session logs
        if LOGS_DIR.exists():
            try:
                # Find all log files for this persona
                pattern = f"{persona_id}_*.csv"
                for log_file in LOGS_DIR.glob(pattern):
                    try:
                        with open(log_file, mode='r', newline='') as f:
                            reader = csv.DictReader(f)
                            all_rows.extend(list(reader))
                    except Exception:
                        continue  # Skip corrupted files
            except Exception:
                pass

        # Fallback to legacy log file if exists
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, mode='r', newline='') as f:
                    reader = csv.DictReader(f)
                    rows = [row for row in reader if row.get('persona') == persona_id]
                    all_rows.extend(rows)
            except Exception:
                pass

        # Sort by timestamp (most recent first) and find last non-login command
        try:
            all_rows.sort(key=lambda r: r.get('timestamp', ''), reverse=True)
            for row in all_rows:
                cmd = row.get('command', '')
                if "login" in cmd.lower():
                    continue
                return cmd
        except Exception:
            pass

        return "none"

    def format_sitrep(self, sitrep: dict[str, Any]) -> str:
        """
        Formats the sitrep data into a beautiful Rich/String display.
        """
        mail_color = "red" if sitrep["unread_mail_count"] > 0 else "green"
        return "\n".join([
            "📡 [bold cyan]SITUATION REPORT (SITREP)[/bold cyan]",
            f"👤 Persona: [green]{sitrep['persona']}[/green]",
            f"🔢 Sequence: [yellow]{sitrep['sequence']}[/yellow] (Next: {sitrep['next_persona']})",
            f"📧 Mail: [{mail_color}]{sitrep['unread_mail_count']} unread[/{mail_color}]",
            f"🛠️  Last Tool: [dim]{sitrep['last_tool_used']}[/dim]",
        ])
