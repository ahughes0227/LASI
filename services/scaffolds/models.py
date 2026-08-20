"""Contracts for governed scaffolding."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from services.contracts.models import StrictModel


class ScaffoldTemplate(StrictModel):
    """Identity and revision of one template under `_scaffolds/`."""

    template: str
    revision: str = Field(pattern=r"^\d+\.\d+$")


class RenderedScaffold(StrictModel):
    """What a render produced, and from which bench.

    The revision is the point of this record.  Two trees generated from different
    revisions are not structurally comparable, and evidence drawn across them is not
    like-for-like unless that difference is visible.
    """

    template: str
    revision: str
    path: str
    answers: dict[str, str] = Field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return Path(self.path)
