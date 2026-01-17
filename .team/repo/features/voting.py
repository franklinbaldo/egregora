import csv
from pathlib import Path
from typing import Dict, List, Optional
import datetime

VOTES_FILE = Path(".team/votes.csv")
SCHEDULE_FILE = Path(".team/schedule.csv")
PERSONAS_ROOT = Path(".team/personas")

class VoteManager:
    def __init__(self, schedule_file: Path = SCHEDULE_FILE, votes_file: Path = VOTES_FILE):
        self.schedule_file = schedule_file
        self.votes_file = votes_file

    def cast_vote(self, voter_sequence: str, candidate_personas: List[str]) -> str:
        """
        Cast ranked votes for personas to occupy a calculated future sequence.
        Stores candidates as comma-separated array in a single column.
        Format: [voter_sequence, sequence_cast, candidates]
        
        If a vote already exists for this voter_sequence, it is OVERWRITTEN.
        """
        roster_size = self._get_roster_size()
        voter_seq_int = int(voter_sequence)
        target_seq_int = voter_seq_int + roster_size + 1
        target_sequence = f"{target_seq_int:03}"

        # Store candidates as comma-separated array
        candidates_array = ",".join(candidate_personas)

        # Read existing votes, filter out any from same voter_sequence
        existing_votes = []
        if self.votes_file.exists():
            with open(self.votes_file, mode='r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Keep votes from OTHER voter sequences
                    if row['voter_sequence'] != voter_sequence:
                        existing_votes.append(row)

        # Write all votes back, with new vote added
        with open(self.votes_file, mode='w', newline='') as f:
            fieldnames = ['voter_sequence', 'sequence_cast', 'candidates']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing_votes)
            writer.writerow({
                'voter_sequence': voter_sequence,
                'sequence_cast': target_sequence,
                'candidates': candidates_array
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
        """Tally votes for a specific sequence from the CSV using Borda Count."""
        if not self.votes_file.exists():
            return {}
            
        roster_size = self._get_roster_size()
        tally = {}
        with open(self.votes_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['sequence_cast'] == sequence_id:
                    # Parse candidates array (comma-separated)
                    candidates_str = row.get('candidates', '')
                    if not candidates_str:
                        continue
                    candidates = [c.strip() for c in candidates_str.split(',')]
                    
                    # Assign Borda points: Rank 1 gets roster_size, Rank 2 gets roster_size - 1, etc.
                    for rank, persona in enumerate(candidates, start=1):
                        points = max(0, roster_size - (rank - 1))
                        tally[persona] = tally.get(persona, 0) + points
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

    def get_upcoming_winners(self, from_sequence: str, count: int = 5) -> List[Dict]:
        """Get current vote winners for upcoming sequences."""
        results = []
        start_seq = int(from_sequence)
        
        for i in range(count):
            seq_id = f"{start_seq + i:03}"
            tally = self.get_tally(seq_id)
            if tally:
                winner = max(tally, key=tally.get)
                results.append({
                    "sequence": seq_id,
                    "winner": winner,
                    "points": tally[winner],
                    "total_votes": sum(tally.values())
                })
            else:
                # Get scheduled persona if no votes
                scheduled = self._get_scheduled_persona(seq_id)
                if scheduled:
                    results.append({
                        "sequence": seq_id,
                        "winner": scheduled,
                        "points": 0,
                        "total_votes": 0,
                        "scheduled": True
                    })
        return results

    def _get_scheduled_persona(self, sequence_id: str) -> Optional[str]:
        """Get the currently scheduled persona for a sequence."""
        if not self.schedule_file.exists():
            return None
        with open(self.schedule_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['sequence'] == sequence_id:
                    return row.get('persona')
        return None

    def validate_schedule_vs_votes(self) -> List[Dict]:
        """Validate that schedule.csv respects vote results. Returns list of violations."""
        violations = []
        if not self.schedule_file.exists() or not self.votes_file.exists():
            return violations
        
        with open(self.schedule_file, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                seq_id = row['sequence']
                scheduled_persona = row.get('persona')
                
                # Skip already executed sequences
                if row.get('session_id') or row.get('pr_status'):
                    continue
                
                tally = self.get_tally(seq_id)
                if tally:
                    winner = max(tally, key=tally.get)
                    if winner != scheduled_persona:
                        violations.append({
                            "sequence": seq_id,
                            "scheduled": scheduled_persona,
                            "voted_winner": winner,
                            "winner_points": tally[winner]
                        })
        return violations
