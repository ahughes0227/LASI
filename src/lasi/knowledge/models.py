"""Local knowledge-service value objects; wire contracts remain canonical."""

from dataclasses import dataclass
from pathlib import Path

from lasi.contracts import KnowledgeDocument


@dataclass(frozen=True, slots=True)
class ParsedKnowledgeDocument:
    """A validated document and its human-readable markdown body."""

    document: KnowledgeDocument
    body: str
    path: Path

    @property
    def epistemic_status(self) -> str:
        """Expose the domain term while retaining the contract's ``status`` field."""
        return self.document.status


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    """Bounded metadata-first retrieval criteria."""

    text: str = ""
    document_type: str | None = None
    modality: str | None = None
    problem_type: str | None = None
    tool: str | None = None
    tags: tuple[str, ...] = ()
    limit: int = 10

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("retrieval limit must be positive")


@dataclass(frozen=True, slots=True)
class RetrievedKnowledge:
    """Auditable retrieval result, including the exact document references used."""

    documents: tuple[ParsedKnowledgeDocument, ...]

    @property
    def refs(self) -> tuple[str, ...]:
        return tuple(item.document.document_id for item in self.documents)
