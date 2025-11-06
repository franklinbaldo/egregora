"""A minimal, line-based editing protocol for Egregora."""

from typing import Annotated, Any

from pydantic import BaseModel


class DocumentSnapshot(BaseModel):
    """A versioned, line-indexed representation of a document for editing."""

    doc_id: Annotated[str, "The unique ID of the document"]
    version: Annotated[int, "The version number of the document"]
    meta: Annotated[dict[str, Any], "Metadata associated with the document"]
    lines: Annotated[dict[int, str], "The lines of the document, indexed by line number"]


class Editor:
    """A class to encapsulate the editor tools."""

    def __init__(self, snapshot: Annotated[DocumentSnapshot, "The initial snapshot of the document"]):
        self.snapshot = snapshot

    def edit_line(
        self,
        expect_version: Annotated[int, "The expected version of the document for optimistic concurrency"],
        index: Annotated[int, "The 0-based index of the line to edit"],
        new: Annotated[str, "The new content for the line"],
    ) -> dict[str, Any]:
        """Replaces a single line in the document."""
        if expect_version != self.snapshot.version:
            return {
                "ok": False,
                "reason": "version_mismatch",
                "current_version": self.snapshot.version,
            }

        if index not in self.snapshot.lines:
            return {
                "ok": False,
                "reason": "index_out_of_bounds",
                "max_index": len(self.snapshot.lines) - 1,
            }

        self.snapshot.lines[index] = new
        self.snapshot.version += 1
        return {"ok": True, "new_version": self.snapshot.version}

    def full_rewrite(
        self,
        expect_version: Annotated[int, "The expected version of the document for optimistic concurrency"],
        content: Annotated[str, "The new, complete content of the document"],
    ) -> dict[str, Any]:
        """Replaces the entire document content."""
        if expect_version != self.snapshot.version:
            return {
                "ok": False,
                "reason": "version_mismatch",
                "current_version": self.snapshot.version,
            }

        if not content:
            return {"ok": False, "reason": "content_empty"}

        lines = content.split("\n")
        self.snapshot.lines = dict(enumerate(lines))
        self.snapshot.version += 1
        return {"ok": True, "new_version": self.snapshot.version, "line_count": len(lines)}

    def finish(
        self,
        expect_version: Annotated[int, "The expected version of the document for optimistic concurrency"],
        decision: Annotated[str, "The decision: 'publish' or 'hold'"],
        notes: Annotated[str, "Notes on the decision"],
    ) -> dict[str, Any]:
        """Marks the document for the publish queue or holds it."""
        if expect_version != self.snapshot.version:
            return {
                "ok": False,
                "reason": "version_mismatch",
                "current_version": self.snapshot.version,
            }

        # This is a placeholder. In a real implementation, this method would
        # interact with a database or a publishing queue to officially record
        # the agent's decision. For now, it just confirms the action.
        return {"ok": True, "decision": decision, "notes": notes}
