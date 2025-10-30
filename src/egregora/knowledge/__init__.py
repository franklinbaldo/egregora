"""Knowledge stage - Stateful learning systems and context management.

This package manages persistent knowledge:
- RAG (Retrieval-Augmented Generation) vector store
- Annotations and conversation metadata
- Content ranking via Elo ratings
"""

from . import rag, ranking
from .annotations import ANNOTATION_AUTHOR, Annotation, AnnotationStore

__all__ = [
    "rag",
    "ranking",
    "AnnotationStore",
    "Annotation",
    "ANNOTATION_AUTHOR",
]
