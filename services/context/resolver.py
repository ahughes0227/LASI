"""Selective minimum-sufficient context assembly."""

from pathlib import Path

from .models import AgentContext, ContextDocument, ContextRequest
from .retrieval import StructuredMemoryRetriever
from .store import ICMStore


class ContextResolver:
    def __init__(
        self, store: ICMStore, *, structured_retriever: StructuredMemoryRetriever | None = None
    ) -> None:
        self.store = store
        self.structured_retriever = structured_retriever

    def resolve(self, request: ContextRequest) -> AgentContext:
        system_root = self.store.system_root
        project_root = self.store.project_root(request.project_id)
        system_paths = list(request.system_paths)
        if request.capability:
            capability_path = f"capabilities/{request.capability}.md"
            if (system_root / capability_path).is_file() and capability_path not in system_paths:
                system_paths.append(capability_path)
        system_candidates = self._select(system_root, system_paths, request.keywords, "system")
        project_paths = self._experiment_project_paths(request, project_root)
        project_candidates = self._select(project_root, project_paths, request.keywords, "project")
        selected = sorted(
            [*system_candidates, *project_candidates],
            key=lambda document: (-document.relevance, document.layer, document.path),
        )[: request.max_documents]
        system = [document for document in selected if document.layer == "system"]
        project = [document for document in selected if document.layer == "project"]
        structured_refs = list(request.structured_memory_refs)
        if self.structured_retriever is not None:
            structured_refs.extend(self.structured_retriever.retrieve_refs(request))
        return AgentContext(
            project_id=request.project_id,
            assignment=request.assignment,
            system_documents=system,
            project_documents=project,
            local_assignment=request.assignment,
            required_inputs=request.required_inputs,
            expected_outputs=request.expected_outputs,
            structured_memory_refs=list(dict.fromkeys(structured_refs)),
        )

    @staticmethod
    def _experiment_project_paths(request: ContextRequest, project_root: Path) -> list[str]:
        if request.experiment_id is None:
            return request.project_paths
        experiment_prefix = f"20_work/experiments/{request.experiment_id}/"
        for path in request.project_paths:
            if path.startswith("20_work/experiments/") and not path.startswith(experiment_prefix):
                raise ValueError(
                    "experiment context cannot include a competing experiment workspace"
                )
        if request.project_paths:
            return request.project_paths
        shared = [
            "00_task/objective.md",
            "00_task/constraints.md",
            "10_context/current_state.md",
            "10_context/dataset_profile.md",
            "10_context/domain_context.md",
            "10_context/prior_findings.md",
        ]
        experiment_root = project_root / experiment_prefix
        experiment_paths = [
            path.relative_to(project_root).as_posix()
            for path in sorted(experiment_root.glob("*.md"))
        ]
        return [*shared, *experiment_paths]

    @staticmethod
    def _select(
        root: Path, explicit: list[str], keywords: list[str], layer: str
    ) -> list[ContextDocument]:
        if not root.exists():
            return []
        terms = {term.lower() for term in keywords if term}
        if explicit:
            candidates = []
            for relative in explicit:
                candidate = (root / relative).resolve()
                if root.resolve() not in candidate.parents:
                    raise ValueError(f"context path escapes layer root: {relative}")
                candidates.append(candidate)
        else:
            candidates = [
                path
                for pattern in ("**/*.md", "**/*.yaml", "**/*.yml")
                for path in root.glob(pattern)
            ]
        ranked: list[tuple[int, Path]] = []
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml"}:
                continue
            content = path.read_text(encoding="utf-8")
            haystack = f"{path.name} {content}".lower()
            score = sum(haystack.count(term) for term in terms) if terms else (1 if explicit else 0)
            if explicit or score:
                ranked.append((score, path))
        ranked.sort(key=lambda item: (-item[0], str(item[1])))
        return [
            ContextDocument(
                path=str(path.relative_to(root)),
                layer=layer,
                content=path.read_text(encoding="utf-8"),
                relevance=score,
            )
            for score, path in ranked
        ]
