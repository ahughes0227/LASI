"""Registration and bounded rule-based retrieval for markdown knowledge."""

from pathlib import Path

from .frontmatter import FrontmatterError, parse_document
from .models import KnowledgeQuery, ParsedKnowledgeDocument, RetrievedKnowledge

_FOLDERS = {
    "facts",
    "policies",
    "hypotheses",
    "lessons",
    "literature",
    "toolbox",
    "taxonomies",
    "templates",
}
_FOLDER_TYPES = {
    "facts": "fact",
    "policies": "policy",
    "hypotheses": "hypothesis",
    "lessons": "lesson",
    "literature": "literature",
    "toolbox": "toolbox",
    "taxonomies": "taxonomy",
    "templates": "template",
}
_STATUS_WEIGHT = {
    "approved": 50,
    "tentative": 30,
    "under_review": 20,
    "draft": 10,
    "contradicted": 5,
    "retired": 0,
}
_EVIDENCE_WEIGHT = {
    "production_confirmed": 30,
    "human_confirmed": 25,
    "repeated_project_pattern": 20,
    "literature_supported": 15,
    "single_project_observation": 10,
    "policy_decision": 20,
    "contradicted_by_later_result": 0,
}


class KnowledgeRegistry:
    """In-memory index rebuilt from the Git-backed knowledge directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._documents: dict[str, ParsedKnowledgeDocument] = {}

    def register_document(self, path: Path) -> ParsedKnowledgeDocument:
        resolved = path.resolve()
        if self.root not in resolved.parents:
            raise FrontmatterError(f"knowledge path is outside registry root: {path}")
        parsed = parse_document(resolved, relative_to=self.root)
        folder = resolved.parent.name
        if folder in _FOLDERS and parsed.document.type != _FOLDER_TYPES[folder]:
            raise FrontmatterError(
                f"document type {parsed.document.type!r} does not match folder {folder!r}"
            )
        previous = self._documents.get(parsed.document.document_id)
        if previous is not None and previous.document.path != parsed.document.path:
            raise FrontmatterError(f"duplicate document_id: {parsed.document.document_id}")
        self._documents[parsed.document.document_id] = parsed
        return parsed

    def register_all(self) -> tuple[ParsedKnowledgeDocument, ...]:
        """Register frontmatter-bearing markdown files, excluding README fixtures."""
        for path in sorted(self.root.glob("**/*.md")):
            if path.name.lower() == "readme.md":
                continue
            self.register_document(path)
        return tuple(self._documents.values())

    def get(self, document_id: str) -> ParsedKnowledgeDocument | None:
        return self._documents.get(document_id)

    def retrieve(self, query: KnowledgeQuery | None = None) -> RetrievedKnowledge:
        """Return at most ``query.limit`` documents using deterministic metadata rules."""
        query = query or KnowledgeQuery()
        query_tags = {tag.lower() for tag in query.tags}
        text_terms = {term.lower() for term in query.text.split() if term}
        ranked: list[tuple[int, str, ParsedKnowledgeDocument]] = []
        for item in self._documents.values():
            document = item.document
            if document.status == "retired" and not query.text:
                continue
            if query.document_type and document.type != query.document_type:
                continue
            if query.modality and query.modality not in document.related_modalities:
                continue
            if query.problem_type and query.problem_type not in document.related_problem_types:
                continue
            if query.tool and query.tool not in document.related_tools:
                continue
            metadata_terms = {tag.lower() for tag in document.tags}
            metadata_terms.update(value.lower() for value in document.related_modalities)
            metadata_terms.update(value.lower() for value in document.related_problem_types)
            metadata_terms.update(value.lower() for value in document.related_tools)
            body_terms = set(item.body.lower().split())
            matched_tags = len(query_tags & metadata_terms)
            matched_text = len(text_terms & (metadata_terms | body_terms))
            if (query_tags and not matched_tags) or (text_terms and not matched_text):
                continue
            score = _STATUS_WEIGHT.get(document.status, 0) + _EVIDENCE_WEIGHT.get(
                document.evidence_level or "", 0
            )
            score += matched_tags * 20 + matched_text * 5
            ranked.append((score, document.document_id, item))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return RetrievedKnowledge(tuple(row[2] for row in ranked[: query.limit]))
