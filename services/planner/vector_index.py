"""Local vector index for planner-catalog candidate discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .catalog import PlannerCatalog
from .models import PlannerCandidate, PlannerCatalogNode

#: On-disk schema. v2 adds the fitted IDF weights, without which a restored
#: query vector is scored against a document matrix built in a different space.
INDEX_FORMAT = "planner-tfidf-v2"


class PlannerVectorIndex:
    """Rebuildable TF-IDF index; graph traversal remains the authority."""

    def __init__(
        self,
        nodes: list[PlannerCatalogNode],
        matrix: np.ndarray,
        vocabulary: dict[str, int],
        idf: np.ndarray,
    ) -> None:
        self.nodes = nodes
        self.matrix = matrix
        self.vectorizer = _fitted_vectorizer(vocabulary, idf)

    @classmethod
    def build(cls, catalog: PlannerCatalog) -> PlannerVectorIndex:
        nodes = sorted(catalog.nodes.values(), key=lambda node: node.node_id)
        vectorizer = TfidfVectorizer(norm="l2")
        documents = [_node_text(node) for node in nodes]
        matrix = vectorizer.fit_transform(documents).toarray().astype(np.float32)
        # The corpus IDF weights are carried with the matrix: a query embedded
        # without them is not comparable to these document vectors.
        return cls(nodes, matrix, dict(vectorizer.vocabulary_), np.asarray(vectorizer.idf_))

    def search(self, query: str, *, limit: int = 12) -> list[PlannerCandidate]:
        query_vector = self.vectorizer.transform([query]).toarray()[0].astype(np.float32)
        scores = self.matrix @ query_vector
        terms = set(query.lower().split())
        results: list[PlannerCandidate] = []
        for index in np.argsort(-scores, kind="stable")[:limit]:
            score = float(scores[index])
            if score <= 0:
                continue
            node = self.nodes[int(index)]
            matched = sorted(term for term in terms if term in _node_text(node).lower())
            results.append(
                PlannerCandidate(node=node, score=round(min(score, 1.0), 6), matched_terms=matched)
            )
        return results

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            target.with_suffix(".npz"), matrix=self.matrix, idf=np.asarray(self.vectorizer.idf_)
        )
        target.with_suffix(".json").write_text(
            json.dumps(
                {
                    "nodes": [node.model_dump(mode="json") for node in self.nodes],
                    "vocabulary": self.vectorizer.vocabulary_,
                    "format": INDEX_FORMAT,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> PlannerVectorIndex:
        target = Path(path)
        metadata: dict[str, Any] = json.loads(
            target.with_suffix(".json").read_text(encoding="utf-8")
        )
        stored_format = metadata.get("format")
        if stored_format != INDEX_FORMAT:
            # A stale index is rebuildable from the authoritative registries;
            # scoring against one silently is not an acceptable fallback.
            raise ValueError(
                f"planner vector index format is {stored_format!r}, expected {INDEX_FORMAT!r}; "
                "rebuild the index from the planner catalog"
            )
        archive = np.load(target.with_suffix(".npz"))
        nodes = [PlannerCatalogNode.model_validate(item) for item in metadata["nodes"]]
        return cls(nodes, archive["matrix"], metadata["vocabulary"], archive["idf"])


def _fitted_vectorizer(vocabulary: dict[str, int], idf: np.ndarray) -> TfidfVectorizer:
    """Restore a transform-ready vectorizer from a persisted vocabulary and IDF."""
    weights = np.asarray(idf, dtype=np.float64)
    if len(vocabulary) != weights.shape[0]:
        raise ValueError(
            f"planner vector index vocabulary has {len(vocabulary)} terms but "
            f"{weights.shape[0]} IDF weights"
        )
    vectorizer = TfidfVectorizer(vocabulary=vocabulary, norm="l2")
    vectorizer.idf_ = weights
    return vectorizer


def _node_text(node: PlannerCatalogNode) -> str:
    return " ".join([node.node_type, node.external_id, *(_string_values(node.payload))])


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _string_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _string_values(child)]
    return []
