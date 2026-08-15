"""Resolution of versioned workflow assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.contracts import AgentProfile, WorkflowDefinition


class WorkflowBindingError(ValueError):
    """A referenced workflow asset is absent or malformed."""


class WorkflowBindings:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _read(self, category: str, asset_id: str, version: str) -> dict[str, Any]:
        path = self.root / category / asset_id / f"{version}.json"
        if not path.is_file():
            raise WorkflowBindingError(f"missing {category} asset: {asset_id}@{version}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise WorkflowBindingError(f"{path} must contain a JSON object")
        return value

    def prompt(self, asset_id: str, version: str) -> dict[str, Any]:
        return self._read("workflow_prompts", asset_id, version)

    def rubric(self, asset_id: str, version: str) -> dict[str, Any]:
        return self._read("reasoning_rubrics", asset_id, version)

    def profile(self, asset_id: str, version: str) -> AgentProfile:
        return AgentProfile.model_validate(self._read("agent_profiles", asset_id, version))

    def validate_references(self, workflow: WorkflowDefinition) -> None:
        for node in workflow.nodes:
            self.prompt(node.prompt.prompt_id, node.prompt.version)
            self.rubric(node.rubric.rubric_id, node.rubric.version)
            if node.agent_profile:
                self.profile(node.agent_profile.prompt_id, node.agent_profile.version)
