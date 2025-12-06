"""Output sinks for V3."""

from egregora_v3.infra.sinks.atom_xml import AtomXMLOutputSink
from egregora_v3.infra.sinks.csv import CSVOutputSink
from egregora_v3.infra.sinks.mkdocs import MkDocsOutputSink
from egregora_v3.infra.sinks.sqlite import SQLiteOutputSink

__all__ = ["AtomXMLOutputSink", "CSVOutputSink", "MkDocsOutputSink", "SQLiteOutputSink"]
