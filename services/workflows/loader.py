"""Discovery and loading of JSON workflow packages."""

from __future__ import annotations

import json
from pathlib import Path

from services.contracts import WorkflowDefinition

from .binding import WorkflowBindings
from .validation import validate_workflow


class WorkflowLoader:
    def __init__(self, root: str | Path, *, asset_root: str | Path = "system") -> None:
        self.root = Path(root)
        self.bindings = WorkflowBindings(asset_root)

    def load(self, workflow_id: str) -> WorkflowDefinition:
        path = self.root / workflow_id / "workflow.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        workflow = WorkflowDefinition.model_validate(json.loads(path.read_text(encoding="utf-8")))
        repository_root = self.root.parent
        skills = {p.name for p in (repository_root / ".opencode/skills").iterdir() if p.is_dir()}
        capabilities = {p.stem for p in (repository_root / "system/capabilities").glob("*.md")}
        prompts = {
            (p.parent.name, p.stem)
            for p in Path(self.bindings.root / "workflow_prompts").glob("*/*.json")
        }
        rubrics = {
            (p.parent.name, p.stem)
            for p in Path(self.bindings.root / "reasoning_rubrics").glob("*/*.json")
        }
        profiles = {
            (p.parent.name, p.stem): self.bindings.profile(p.parent.name, p.stem)
            for p in Path(self.bindings.root / "agent_profiles").glob("*/*.json")
        }
        validate_workflow(
            workflow,
            skills=skills,
            capabilities=capabilities,
            prompts=prompts,
            rubrics=rubrics,
            profiles=profiles,
        )
        self.bindings.validate_references(workflow)
        return workflow

    def discover(self) -> tuple[str, ...]:
        return tuple(sorted(path.parent.name for path in self.root.glob("*/workflow.json")))
