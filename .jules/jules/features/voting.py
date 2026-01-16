import json
import csv
from pathlib import Path
from typing import Dict, List, Optional
import datetime

VOTES_ROOT = Path(".jules/votes")
SCHEDULE_FILE = Path(".jules/schedule.csv")

class VoteManager:
    def __init__(self, schedule_file: Path = SCHEDULE_FILE):
        self.schedule_file = schedule_file
        self.votes_root = VOTES_ROOT

    def cast_vote(self, sequence_id: str, voter_id: str, persona_id: str):
        """
        Cast a vote for a persona to occupy a specific sequence.
        """
        # Validate sequence isn't already executed
        if self._is_sequence_executed(sequence_id):
            raise ValueError(f"Sequence {sequence_id} has already been executed or is in progress.")

        seq_dir = self.votes_root / sequence_id
        seq_dir.mkdir(parents=True, exist_ok=True)
        
        vote_file = seq_dir / f"{voter_id}.json"
        vote_data = {
            "voter": voter_id,
            "persona": persona_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        vote_file.write_text(json.dumps(vote_data, indent=2))

    def _is_sequence_executed(self, sequence_id: str) -> bool:
        """
        Check if a sequence in schedule.csv has a session_id or pr_status.
        """
        if not self.schedule_file.exists():
            return False
            
        with open(self.schedule_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['sequence'] == sequence_id:
                    # If session_id or pr_status is present, it's executed or in progress
                    return bool(row.get('session_id') or row.get('pr_status'))
        return False

    def get_tally(self, sequence_id: str) -> Dict[str, int]:
        """
        Tally votes for a specific sequence.
        """
        seq_dir = self.votes_root / sequence_id
        if not seq_dir.exists():
            return {}
            
        tally = {}
        for vote_file in seq_dir.glob("*.json"):
            try:
                data = json.loads(vote_file.read_text())
                persona = data.get("persona")
                if persona:
                    tally[persona] = tally.get(persona, 0) + 1
            except Exception:
                continue
        return tally

    def apply_votes(self, sequence_id: str) -> Optional[str]:
        """
        Find the winner for a sequence and update schedule.csv.
        Returns the winning persona ID if updated.
        """
        tally = self.get_tally(sequence_id)
        if not tally:
            return None
            
        # Get persona with most votes. If tie, first one found wins.
        winner = max(tally, key=tally.get)
        
        if self._update_schedule(sequence_id, winner):
            return winner
        return None

    def _update_schedule(self, sequence_id: str, persona_id: str) -> bool:
        """
        Update the persona for a specific sequence in schedule.csv.
        Only updates if the sequence is NOT executed.
        """
        if not self.schedule_file.exists():
            return False
            
        updated = False
        rows = []
        headers = []
        
        with open(self.schedule_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for row in reader:
                if row['sequence'] == sequence_id:
                    if not (row.get('session_id') or row.get('pr_status')):
                        row['persona'] = persona_id
                        updated = True
                rows.append(row)
                
        if updated:
            with open(self.schedule_file, mode='w', newline='') as f:
                writer = csv.DictReader(f, fieldnames=headers) # Error here, should be DictWriter
                # Correcting to DictWriter
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
                
        return updated
