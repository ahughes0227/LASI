"""Durable bridge from background assignment escalations to the OpenCode UI."""

from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts import CoordinatorDirective, ResearchAssignment


class OpenCodeUINotifier:
    """Publish pending escalations for the project OpenCode plugin to surface."""

    def __init__(self, workspace: Path) -> None:
        self.directory = workspace.resolve() / ".lasi" / "notifications"

    def publish_escalation(
        self, assignment: ResearchAssignment, directive: CoordinatorDirective
    ) -> Path:
        if directive.action != "escalate":
            raise ValueError("only escalation directives may create UI notifications")
        assert directive.escalation_id is not None
        assert directive.escalation_question is not None
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{_safe_id(directive.escalation_id)}.json"
        temporary = path.with_suffix(f".json.{os.getpid()}.tmp")
        payload = {
            "schema_version": "1.0",
            "type": "lasi_escalation",
            "assignment_id": assignment.assignment_id,
            "project_id": assignment.project_id,
            "escalation_id": directive.escalation_id,
            "question": directive.escalation_question,
            "feedback_command": (
                f"/lasi-feedback {assignment.assignment_id} "
                f"{directive.escalation_id} <your feedback>"
            ),
        }
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return path

    def clear_escalation(self, escalation_id: str) -> None:
        path = self.directory / f"{_safe_id(escalation_id)}.json"
        path.unlink(missing_ok=True)


def _safe_id(value: str) -> str:
    if not value or any(
        character not in "-_.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for character in value
    ):
        raise ValueError("escalation id contains unsafe filename characters")
    return value
