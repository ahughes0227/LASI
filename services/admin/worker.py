"""Internal detached worker entrypoint; OpenCode commands remain the user surface."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.runtime import OpenCodeTaskInvoker, TaskExecutor, TaskRuntimeService
from services.tools import ToolRegistry, register_builtin_tools

from .service import open_admin_service


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--assignment-id", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    admin = open_admin_service(database_url=args.database_url, workspace=workspace)
    tools = register_builtin_tools(ToolRegistry())
    runtime = TaskRuntimeService(admin.memory, available_tools=tools.all())
    runtime.install_default_rubrics()
    executor = TaskExecutor(
        runtime,
        OpenCodeTaskInvoker(workspace),
        executor_id=f"local-runtime:{args.assignment_id}",
    )
    while True:
        status = admin.status(args.assignment_id).assignment
        if status.cancel_requested:
            admin.cancel(args.assignment_id)
            return 0
        if status.pause_requested:
            admin.pause(args.assignment_id)
            return 0
        if status.status in {
            "budget_exhausted",
            "cancelled",
            "completed",
            "failed",
            "paused",
            "escalated",
        }:
            return 1 if status.status == "failed" else 0
        result = executor.run_once(args.assignment_id)
        if result == "idle":
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
