"""Record generated trees in operational memory.

Separate from `ScaffoldService` so that rendering does not require a database: package
builders scaffold into temporary directories during validation, and those renders are not
part of the durable record.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from services.memory import OperationalMemory
from services.memory.models import ScaffoldRegistration

from .models import RenderedScaffold


class ScaffoldRegistry:
    """Durable index of which template revision produced which tree."""

    def __init__(self, memory: OperationalMemory, *, repository_root: Path | None = None) -> None:
        self.memory = memory
        #: Paths are stored repository-relative where possible so a record stays
        #: meaningful on a machine with a different checkout location.
        self.repository_root = repository_root or Path(__file__).resolve().parents[2]

    def register(
        self, rendered: RenderedScaffold, *, project_id: str | None = None
    ) -> ScaffoldRegistration:
        return self.memory.add(
            ScaffoldRegistration(
                scaffold_registration_id=f"scaffold-{uuid4().hex}",
                template=rendered.template,
                revision=rendered.revision,
                path=self._relative(rendered.directory),
                project_id=project_id,
            )
        )

    def for_template(self, template: str) -> list[ScaffoldRegistration]:
        return [
            item for item in self.memory.list_all(ScaffoldRegistration) if item.template == template
        ]

    def outdated(self, template: str, current_revision: str) -> list[ScaffoldRegistration]:
        """Trees still on an older revision of `template`.

        The set a governed template update would have to act on, which is why the
        revision is recorded rather than inferred.
        """
        return [item for item in self.for_template(template) if item.revision != current_revision]

    def _relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.repository_root))
        except ValueError:
            return str(path.resolve())
