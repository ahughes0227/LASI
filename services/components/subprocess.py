"""Minimal registered subprocess binding for non-Python components."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.core import COMPONENT_ENVIRONMENT_ALLOWLIST, build_child_environment

from .execution import ComponentExecutionContext, ComponentRunOutput

#: Matches `services.tools.runner.DEFAULT_TOOL_TIMEOUT_SECONDS`.  A binding with
#: no bound waits forever, so a component that loops holds its worker until the
#: process is killed by hand.  Every registration gets a wall-clock ceiling.
DEFAULT_COMPONENT_TIMEOUT_SECONDS = 3600.0


@dataclass(frozen=True)
class SubprocessBinding:
    """Trusted registration-time command; invocation configuration cannot change it."""

    command: tuple[str, ...]
    timeout_seconds: float = DEFAULT_COMPONENT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("component timeout_seconds must be a positive wall-clock bound")

    def __call__(self, context: ComponentExecutionContext) -> ComponentRunOutput:
        invocation_path = context.workdir / "invocation.json"
        result_path = context.workdir / "result.json"
        invocation_path.write_text(
            json.dumps(
                {
                    "node_id": context.node_id,
                    "project_id": context.project_id,
                    "dataset_version_id": context.dataset_version_id,
                    "random_seed": context.random_seed,
                    "config": _json_value(context.config),
                    "inputs": {name: str(path) for name, path in context.inputs.items()},
                    "result_path": str(result_path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [*self.command, str(invocation_path)],
            cwd=context.workdir,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
            env=build_child_environment(COMPONENT_ENVIRONMENT_ALLOWLIST),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"component subprocess failed with exit code {completed.returncode}: "
                f"{completed.stderr.strip()}"
            )
        if not result_path.is_file():
            raise FileNotFoundError("component subprocess did not produce result.json")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("component subprocess result must be an object")
        outputs = result.get("outputs", {})
        if not isinstance(outputs, dict):
            raise ValueError("component subprocess outputs must be an object")
        return ComponentRunOutput(
            outputs={
                name: _under_workdir(context.workdir, value) for name, value in outputs.items()
            },
            metrics=result.get("metrics", {}),
            warnings=[completed.stderr] if completed.stderr.strip() else result.get("warnings", []),
        )


def _under_workdir(workdir: Path, value: Any) -> Path:
    path = (workdir / str(value)).resolve()
    if workdir.resolve() not in path.parents:
        raise ValueError(f"subprocess output escapes component workdir: {value}")
    return path


def _json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value
