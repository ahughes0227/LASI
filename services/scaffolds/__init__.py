"""Governed scaffolding: one template per kind of workspace, one way to render it."""

from .models import RenderedScaffold, ScaffoldTemplate
from .registry import ScaffoldRegistry
from .service import ScaffoldError, ScaffoldService

__all__ = [
    "RenderedScaffold",
    "ScaffoldError",
    "ScaffoldRegistry",
    "ScaffoldService",
    "ScaffoldTemplate",
]
