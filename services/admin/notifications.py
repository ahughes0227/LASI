"""Durable bridge from background assignment escalations to the OpenCode UI."""

from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts import ResearchAssignment


class OpenCodeUINotifier:
    """Publish pending escalations for the project OpenCode plugin to surface."""

    def __init__(self, workspace: Path) -> None:
        self.directory = workspace.resolve() / ".lasi" / "notifications"

    def publish_escalation(self, assignment: ResearchAssignment) -> Path:
        """Write the pending escalation an assignment is already carrying.

        The assignment record is the source of truth for what was asked, so the
        notification is a projection of durable state rather than a second
        place an escalation can be declared.
        """
        if assignment.status != "escalated":
            raise ValueError("only an escalated assignment may create a UI notification")
        escalation_id = assignment.pending_escalation_id
        question = assignment.pending_escalation_question
        if not escalation_id or not question:
            raise ValueError("escalated assignment is missing its escalation id or question")
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{_safe_id(escalation_id)}.json"
        temporary = path.with_suffix(f".json.{os.getpid()}.tmp")
        payload = {
            "schema_version": "1.0",
            "type": "lasi_escalation",
            "assignment_id": assignment.assignment_id,
            "project_id": assignment.project_id,
            "escalation_id": escalation_id,
            "question": question,
            "feedback_command": (
                f"/lasi-feedback {assignment.assignment_id} {escalation_id} <your feedback>"
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
