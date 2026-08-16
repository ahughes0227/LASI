"""Tests for local planner vectorization."""

import json

import pytest
from services.planner.catalog import PlannerCatalog
from services.planner.models import PlannerCatalogNode
from services.planner.vector_index import PlannerVectorIndex


def _node(external_id: str, description: str) -> PlannerCatalogNode:
    return PlannerCatalogNode(
        node_id=f"component:{external_id}@1.0.0",
        node_type="component",
        external_id=external_id,
        payload={"description": description},
    )


EMBEDDING = _node("embedding_generator", "Generate embeddings for point cloud samples.")
REPORT = _node("report", "Render a static HTML report.")
SPLIT = _node("split", "Split a tabular dataset into train and validation folds.")


def test_vector_index_retrieves_semantically_related_planner_nodes(tmp_path) -> None:
    index = PlannerVectorIndex.build(PlannerCatalog([EMBEDDING, REPORT], []))

    top = index.search("point cloud embedding generation")[0]
    assert top.node.external_id == "embedding_generator"

    index.save(tmp_path / "planner_catalog_vectors")
    loaded = PlannerVectorIndex.load(tmp_path / "planner_catalog_vectors")
    assert loaded.search("static HTML report")[0].node.external_id == "report"


def test_reloaded_index_scores_identically_to_the_index_that_built_it(tmp_path) -> None:
    """A restored query vector must live in the same IDF space as the document matrix."""
    index = PlannerVectorIndex.build(PlannerCatalog([EMBEDDING, REPORT, SPLIT], []))
    index.save(tmp_path / "vectors")
    loaded = PlannerVectorIndex.load(tmp_path / "vectors")

    for query in (
        "point cloud embedding generation",
        "static HTML report",
        "train validation split",
    ):
        original = [(item.node.external_id, item.score) for item in index.search(query)]
        restored = [(item.node.external_id, item.score) for item in loaded.search(query)]
        assert original, query
        assert original == restored, query


def test_stale_index_format_is_rejected_rather_than_scored(tmp_path) -> None:
    PlannerVectorIndex.build(PlannerCatalog([REPORT], [])).save(tmp_path / "vectors")
    metadata_path = (tmp_path / "vectors").with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["format"] = "planner-tfidf-v1"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="rebuild the index"):
        PlannerVectorIndex.load(tmp_path / "vectors")
