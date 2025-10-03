"""Tokenisation and similarity helpers for the RAG implementation."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, Mapping

TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
STOP_WORDS = {
    "a",
    "as",
    "ao",
    "aos",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "no",
    "na",
    "nas",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "que",
    "um",
    "uma",
    "uns",
    "umas",
    "se",
    "ser",
    "será",
    "é",
    "são",
    "foi",
    "são",
    "daqui",
    "dali",
    "sobre",
}


def tokenize(text: str) -> list[str]:
    """Tokenize *text* into lowercase words removing stop words."""

    tokens = [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
    return [token for token in tokens if token not in STOP_WORDS]


def term_frequency(tokens: Iterable[str]) -> Counter[str]:
    """Return a counter with term frequencies."""

    counter: Counter[str] = Counter()
    counter.update(token for token in tokens if token)
    return counter


def inverse_document_frequency(documents: Iterable[Counter[str]]) -> Dict[str, float]:
    """Compute IDF weights for the supplied documents."""

    doc_list = list(documents)
    total_docs = len(doc_list)
    if total_docs == 0:
        return {}

    document_frequency: Counter[str] = Counter()
    for doc in doc_list:
        document_frequency.update(doc.keys())

    return {
        term: math.log((1 + total_docs) / (1 + freq)) + 1.0
        for term, freq in document_frequency.items()
    }


def build_vector(tf: Mapping[str, float], idf: Mapping[str, float]) -> Dict[str, float]:
    """Build a TF-IDF vector normalised to unit length."""

    vector = {term: tf[term] * idf.get(term, 0.0) for term in tf}
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm == 0.0:
        return vector
    return {term: value / norm for term, value in vector.items()}


def cosine_similarity(vec_a: Mapping[str, float], vec_b: Mapping[str, float]) -> float:
    """Return the cosine similarity between two sparse vectors."""

    if not vec_a or not vec_b:
        return 0.0

    # iterate over smallest dict
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a

    return sum(value * vec_b.get(term, 0.0) for term, value in vec_a.items())


def build_query_vector(query: str, idf: Mapping[str, float]) -> Dict[str, float]:
    """Tokenize *query* and return the TF-IDF vector using *idf*."""

    tokens = tokenize(query)
    tf = term_frequency(tokens)
    if not tf:
        return {}
    return build_vector(tf, idf)
