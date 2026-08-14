"""Focused tests for semantic-memory parsing, retrieval, and governance."""

from datetime import date
from pathlib import Path

import pytest
from services.contracts import KnowledgeProposal
from services.knowledge import (
    FrontmatterError,
    KnowledgeCurator,
    KnowledgeQuery,
    KnowledgeRegistry,
    parse_frontmatter,
)


def _document(document_id: str = "d1", **extra: object) -> str:
    fields = {
        "document_id": document_id,
        "type": "lesson",
        "status": "approved",
        "owner": "team",
        "created_at": date(2026, 1, 1),
        "tags": ["label_ambiguity"],
        "evidence_level": "human_confirmed",
    }
    fields.update(extra)
    lines = ["---"] + [f"{key}: {value}" for key, value in fields.items()] + ["---", "# Claim", ""]
    return "\n".join(lines)


def test_frontmatter_maps_epistemic_status_and_rejects_unknown_fields() -> None:
    metadata, body = parse_frontmatter(
        _document().replace("status: approved", "epistemic_status: approved")
    )
    assert metadata["status"] == "approved"
    assert body.startswith("# Claim")
    with pytest.raises(FrontmatterError, match="unsupported"):
        parse_frontmatter(_document().replace("owner: team", "unknown: value\nowner: team"))


def test_registry_registers_and_retrieves_bounded_references(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "lessons" / "lesson.md"
    path.parent.mkdir()
    path.write_text(_document(), encoding="utf-8")
    registry = KnowledgeRegistry(root)
    registry.register_all()
    result = registry.retrieve(KnowledgeQuery(tags=("label_ambiguity",), limit=1))
    assert result.refs == ("d1",)


def test_high_consequence_proposals_cannot_be_auto_approved() -> None:
    proposal = KnowledgeProposal(
        proposal_id="p1",
        proposal_type="hypothesis_promotion",
        source="curator",
        title="Promote",
        summary="s",
        rationale="r",
        status="draft",
    )
    assert KnowledgeCurator().propose(proposal).approval_required
    with pytest.raises(ValueError, match="require human approval"):
        KnowledgeCurator().propose(proposal.model_copy(update={"status": "approved"}))


@pytest.mark.parametrize(
    "proposal_type",
    [
        "new_lesson",
        "lesson_retirement",
        "new_literature_summary",
        "new_taxonomy_entry",
        "new_template",
    ],
)
def test_governed_knowledge_transitions_cannot_be_auto_approved(proposal_type: str) -> None:
    proposal = KnowledgeProposal(
        proposal_id="p1",
        proposal_type=proposal_type,
        source="curator",
        title="Change",
        summary="s",
        rationale="r",
        status="approved",
    )
    with pytest.raises(ValueError, match="governed knowledge transitions"):
        KnowledgeCurator().propose(proposal)
