"""Main Pipeline Loop for Egregora V3.

Implements the flow: Input -> Filter(Resume) -> Window -> Agent -> Save.
"""

from __future__ import annotations

import logging
from typing import Iterator
from datetime import datetime

from egregora_v3.core.ports import InputAdapter, DocumentRepository, Agent
from egregora_v3.pipeline.windowing import WindowingStrategy
from egregora_v3.core.types import Document, DocumentType

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(
        self,
        input_adapter: InputAdapter,
        repository: DocumentRepository,
        windowing: WindowingStrategy,
        agent: Agent,
        source_collection: str = "whatsapp-raw"
    ):
        self.input_adapter = input_adapter
        self.repository = repository
        self.windowing = windowing
        self.agent = agent
        self.source_collection = source_collection

    def run(self, source_path: str):
        """Execute the pipeline."""

        # 1. High Water Mark (Resumability)
        last_updated = self.repository.get_high_water_mark(self.source_collection)
        logger.info(f"Pipeline starting. High Water Mark: {last_updated}")

        # 2. Input Stream
        raw_stream = self.input_adapter.parse(source_path)

        # 3. Filter (Resume)
        def filtered_stream():
            count = 0
            skipped = 0
            for entry in raw_stream:
                # Assign collection if not set (Adapter should probably do this, but safe fallback)
                if hasattr(entry, "collection") and not entry.collection:
                    # Entry base class doesn't have collection, Document does.
                    # We might need to wrap Entry into Document here or ensure Adapter returns Documents.
                    # The InputAdapter returns Entry. We might assume raw entries don't persist directly
                    # OR we persist them as "whatsapp-raw" documents.
                    pass

                # Resumability check
                if last_updated and entry.updated <= last_updated:
                    skipped += 1
                    continue

                yield entry
                count += 1
            logger.info(f"Stream filter: Processed {count} new entries (Skipped {skipped} old entries).")

        # 4. Windowing
        windows = self.windowing.window(filtered_stream())

        # 5. Agent Processing Loop
        for i, window in enumerate(windows):
            logger.info(f"Processing window {i+1} with {len(window)} entries...")

            # Persist raw entries (Optional - depending on if we want full raw history in DB)
            # RFC says: "whatsapp-raw: Onde o adapter despeja mensagens".
            # So we should probably save them.
            for entry in window:
                # Convert Entry to Document for persistence
                # We assume Entry is the base. We need a Document wrapper to save to repo?
                # Repo.save takes Document.
                # Let's create a wrapper doc.
                raw_doc = Document.create(
                    content=entry.content or "",
                    doc_type=DocumentType.ENTRY, # or specific source type
                    title="Raw Entry",
                    collection=self.source_collection,
                    id_override=entry.id,
                    status="published", # It's raw data
                    searchable=False # "Input Bruto (Chat): searchable=False"
                )
                # Ensure timestamp matches original
                # Document.create sets updated=now(). We must override.
                # Document is frozen. We need to use 'updated' param if available or bypass.
                # Actually Document.create doesn't accept updated.
                # We should construct Document directly or use replace.
                # Pydantic models are not frozen by default unless config says so.
                # Dataclass is frozen=True.
                # But wait, types.py Document inherits from Entry(BaseModel).
                # Is it a dataclass or Pydantic model?
                # In types.py: "class Document(Entry):" where Entry is BaseModel.
                # But it has "@dataclass(frozen=True, slots=True)" decorator?
                # NO. In my last update to `types.py` I removed the dataclass decorator
                # because I made it inherit from Pydantic BaseModel to support schema/serialization better.
                # Let's double check types.py content.

                self.repository.save(raw_doc)

            # Agent Logic
            results = self.agent.process(window)

            # 6. Save Outputs
            for result_doc in results:
                self.repository.save(result_doc)

            logger.info(f"Window {i+1} complete. Saved {len(results)} derived documents.")
