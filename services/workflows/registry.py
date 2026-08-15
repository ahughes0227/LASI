"""Registry of validated installed workflow packages."""

from pathlib import Path

from services.contracts import WorkflowDefinition

from .loader import WorkflowLoader


class WorkflowRegistry:
    def __init__(
        self, root: str | Path = "_workflows", *, asset_root: str | Path = "system"
    ) -> None:
        self.loader = WorkflowLoader(root, asset_root=asset_root)
        self._items: dict[tuple[str, str], WorkflowDefinition] = {}

    def install(self, workflow_id: str) -> WorkflowDefinition:
        workflow = self.loader.load(workflow_id)
        key = (workflow.workflow_id, workflow.version)
        current = self._items.get(key)
        if current is not None and current != workflow:
            raise ValueError(
                f"workflow version is immutable: {workflow.workflow_id}@{workflow.version}"
            )
        self._items[key] = workflow
        return workflow

    def install_all(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(self.install(workflow_id) for workflow_id in self.loader.discover())

    def all(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(
            sorted(self._items.values(), key=lambda item: (item.workflow_id, item.version))
        )

    def get(self, workflow_id: str, version: str | None = None) -> WorkflowDefinition:
        matches = [
            item
            for (item_id, item_version), item in self._items.items()
            if item_id == workflow_id and (version is None or item_version == version)
        ]
        if not matches:
            raise KeyError(workflow_id)
        return sorted(matches, key=lambda item: item.version)[-1]
