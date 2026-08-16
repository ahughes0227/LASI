"""Typed planner-catalog records and query results."""

from typing import Any

from pydantic import BaseModel, Field


class PlannerCatalogNode(BaseModel):
    node_id: str
    node_type: str
    external_id: str
    version: str | None = None
    lifecycle: str = "approved"
    payload: dict[str, Any] = Field(default_factory=dict)


class PlannerCatalogEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    status: str = "active"


class PlannerCandidate(BaseModel):
    node: PlannerCatalogNode
    score: float = Field(ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)


class PlannerPath(BaseModel):
    node_ids: list[str]
    edge_types: list[str]
