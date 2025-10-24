"""A minimal, line-based editing protocol for Egregora."""

from typing import Any, Dict
from pydantic import BaseModel


class DocumentSnapshot(BaseModel):
    """
    A versioned, line-indexed representation of a document for editing.
    """
    doc_id: str
    version: int
    meta: Dict[str, Any]
    lines: Dict[int, str]


class Editor:
    """
    A class to encapsulate the editor tools.
    """

    def __init__(self, snapshot: DocumentSnapshot):
        self.snapshot = snapshot

    def edit_line(self, expect_version: int, index: int, new: str) -> Dict[str, Any]:
        """
        Replaces a single line in the document.
        """
        if expect_version != self.snapshot.version:
            return {"ok": False, "reason": "version_mismatch", "current_version": self.snapshot.version}

        self.snapshot.lines[index] = new
        self.snapshot.version += 1
        return {"ok": True, "new_version": self.snapshot.version}

    def full_rewrite(self, expect_version: int, content: str) -> Dict[str, Any]:
        """
        Replaces the entire document content.
        """
        if expect_version != self.snapshot.version:
            return {"ok": False, "reason": "version_mismatch", "current_version": self.snapshot.version}

        lines = content.split('\n')
        self.snapshot.lines = {i: line for i, line in enumerate(lines)}
        self.snapshot.version += 1
        return {"ok": True, "new_version": self.snapshot.version, "line_count": len(lines)}

    def finish(self, expect_version: int, decision: str, notes: str) -> Dict[str, Any]:
        """
        Marks the document for the publish queue or holds it.
        """
        if expect_version != self.snapshot.version:
            return {"ok": False, "reason": "version_mismatch", "current_version": self.snapshot.version}

        # This is a placeholder. In a real implementation, this method would
        # interact with a database or a publishing queue to officially record
        # the agent's decision. For now, it just confirms the action.
        return {"ok": True, "decision": decision, "notes": notes}
