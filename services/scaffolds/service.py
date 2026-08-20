"""Render governed templates.

`copier copy` is never a supported operation against these templates.  Every render goes
through this service so that the template revision is recorded in the tree, and so that
callers with their own authority rules — a frozen build plan, a project approval — keep
those rules rather than having a second, ungoverned way to create a package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import RenderedScaffold, ScaffoldTemplate

#: Templates live in the repository rather than in a package directory: they are edited
#: as content, reviewed as content, and versioned with the code that renders them.
DEFAULT_SCAFFOLD_ROOT = Path(__file__).resolve().parents[2] / "_scaffolds"

#: Written into every rendered tree by the template itself.
REVISION_FILE = ".scaffold.yml"


class ScaffoldError(RuntimeError):
    """A template is missing, malformed, or was asked to overwrite existing work."""


class ScaffoldService:
    """Renders a named template into a destination that does not yet exist."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_SCAFFOLD_ROOT

    def available(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            item.name
            for item in self.root.iterdir()
            if item.is_dir() and (item / "scaffold.yml").is_file()
        )

    def describe(self, template: str) -> ScaffoldTemplate:
        """Read a template's declared identity and revision."""
        manifest = self.root / template / "scaffold.yml"
        if not manifest.is_file():
            raise ScaffoldError(f"unknown scaffold template: {template}")
        loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ScaffoldError(f"malformed scaffold manifest: {manifest}")
        declared = ScaffoldTemplate.model_validate(loaded)
        if declared.template != template:
            raise ScaffoldError(
                f"scaffold manifest declares {declared.template!r} but lives in {template!r}"
            )
        return declared

    def render(
        self,
        template: str,
        destination: str | Path,
        *,
        data: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> RenderedScaffold:
        """Render `template` into `destination`.

        Refuses a destination that already exists unless `overwrite` is set, which is
        reserved for a governed update rather than offered as a convenience.
        """
        declared = self.describe(template)
        target = Path(destination).resolve()
        if target.exists() and not overwrite:
            if any(target.iterdir()):
                raise ScaffoldError(f"destination already exists: {target}")

        answers: dict[str, Any] = dict(data or {})
        answers["scaffold_template"] = declared.template
        answers["scaffold_revision"] = declared.revision

        self._run_copier(self.root / template, target, answers, overwrite=overwrite)
        self._verify_revision(target, declared)
        return RenderedScaffold(
            template=declared.template,
            revision=declared.revision,
            path=str(target),
            answers={key: str(value) for key, value in answers.items()},
        )

    def revision_of(self, path: str | Path) -> ScaffoldTemplate:
        """Read the revision a rendered tree was generated from."""
        marker = Path(path) / REVISION_FILE
        if not marker.is_file():
            raise ScaffoldError(f"no {REVISION_FILE} in {path}; tree was not rendered by scaffolds")
        loaded = yaml.safe_load(marker.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ScaffoldError(f"malformed {REVISION_FILE} in {path}")
        return ScaffoldTemplate.model_validate(loaded)

    def is_current(self, path: str | Path) -> bool:
        """Whether a rendered tree matches the template's current revision."""
        recorded = self.revision_of(path)
        return recorded.revision == self.describe(recorded.template).revision

    @staticmethod
    def _run_copier(
        source: Path, target: Path, answers: dict[str, Any], *, overwrite: bool
    ) -> None:
        # Imported here so that the dependency is paid only by callers that scaffold.
        from copier import run_copy

        try:
            run_copy(
                str(source),
                str(target),
                data=answers,
                defaults=True,
                unsafe=False,
                overwrite=overwrite,
                quiet=True,
            )
        except Exception as exc:  # copier raises a wide range of its own error types
            raise ScaffoldError(f"failed to render {source.name} into {target}: {exc}") from exc

    def _verify_revision(self, target: Path, declared: ScaffoldTemplate) -> None:
        """A tree whose revision is missing or wrong is not attributable, so refuse it."""
        recorded = self.revision_of(target)
        if (recorded.template, recorded.revision) != (declared.template, declared.revision):
            raise ScaffoldError(
                f"rendered tree records {recorded.template}@{recorded.revision} "
                f"but was rendered from {declared.template}@{declared.revision}"
            )
