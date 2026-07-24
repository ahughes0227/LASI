"""Git-backed semantic knowledge services."""

from .frontmatter import FrontmatterError, parse_document, parse_frontmatter
from .models import KnowledgeQuery, ParsedKnowledgeDocument, RetrievedKnowledge
from .proposals import KnowledgeCurator, proposal_requires_human_approval, validate_proposal
from .registry import KnowledgeRegistry

__all__ = [
    "FrontmatterError",
    "KnowledgeCurator",
    "KnowledgeQuery",
    "KnowledgeRegistry",
    "ParsedKnowledgeDocument",
    "RetrievedKnowledge",
    "parse_document",
    "parse_frontmatter",
    "proposal_requires_human_approval",
    "validate_proposal",
]
