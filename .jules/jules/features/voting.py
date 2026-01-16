import csv
from pathlib import Path
from typing import Dict, List, Optional
import datetime

VOTES_FILE = Path(".jules/votes.csv")
SCHEDULE_FILE = Path(".jules/schedule.csv")
PERSONAS_ROOT = Path(".jules/personas")

class VoteManager:
    def __init__(self, schedule_file: Path = SCHEDULE_FILE, votes_file: Path = VOTES_FILE):
        self.schedule_file = schedule_file
        self.votes_file = votes_file

    def cast_vote(self, voter_sequence: str, candidate_persona: str):
        """
        Cast a vote for a persona to occupy a calculated future sequence.
        [voter_sequence, sequence_cast, candidate_persona_choosed]
        """
        roster_size = self._get_roster_size()
        voter_seq_int = int(voter_sequence)
        target_seq_int = voter_seq_int + roster_size + 1
        target_sequence = f"{target_seq_int:03}"

        # Validate target sequence isn't already executed (though it should be far in the future)
        if self._is_sequence_executed(target_sequence):
             # For these look-ahead votes, it's unlikely to be executed, but safety first.
             pass

        file_exists = self.votes_file.exists()
        with open(self.votes_file, mode='a', newline='') as f:
            fieldnames = ['voter_sequence', 'sequence_cast', 'candidate_persona_choosed']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                'voter_sequence': voter_sequence,
                'sequence_cast': target_sequence,
                'candidate_persona_choosed': candidate_persona
            })
        return target_sequence

    def _get_roster_size(self) -> int:
        """Count active persona directories."""
        if not PERSONAS_ROOT.exists():
            return 0
        return len([d for d in PERSONAS_ROOT.iterdir() if d.is_dir()])

    def _is_sequence_executed(self, sequence_id: str) -> bool:
        """Check if a sequence in schedule.csv has a session_id or pr_status."""
        if not self.schedule_file.exists():
            return False
            
        with open(self.schedule_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['sequence'] == sequence_id:
                    return bool(row.get('session_id') or row.get('pr_status'))
        return False

    def get_tally(self, sequence_id: str) -> Dict[str, int]:
        """Tally votes for a specific sequence from the CSV."""
        if not self.votes_file.exists():
            return {}
            
        tally = {}
        with open(self.votes_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['sequence_cast'] == sequence_id:
                    persona = row['candidate_persona_choosed']
                    tally[persona] = tally.get(persona, 0) + 1
        return tally

    def apply_votes(self, sequence_id: str) -> Optional[str]:
        """Find the winner for a sequence and update schedule.csv."""
        tally = self.get_tally(sequence_id)
        if not tally:
            return None
            
        winner = max(tally, key=tally.get)
        if self._update_schedule(sequence_id, winner):
            return winner
        return None

    def _update_schedule(self, sequence_id: str, persona_id: str) -> bool:
        """Update the persona for a specific sequence in schedule.csv."""
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
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
                
        return updated

    def get_current_sequence(self, persona_id: str) -> Optional[str]:
        """Find the most recent active or started sequence for a persona."""
        if not self.schedule_file.exists():
            return None
            
        # We look for the latest entry for this persona that has a session_id 
        # (meaning it's the current session)
        latest_seq = None
        with open(self.schedule_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['persona'] == persona_id and row.get('session_id'):
                    latest_seq = row['sequence']
        return latest_seq
