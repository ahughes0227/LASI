"""Internal detached worker entrypoint; OpenCode commands remain the user surface."""

from __future__ import annotations

import argparse
from pathlib import Path

from .notifications import OpenCodeUINotifier
from .runner import OpenCodeCoordinatorInvoker, ProjectRunner
from .service import open_admin_service


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--assignment-id", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    admin = open_admin_service(database_url=args.database_url, workspace=workspace)
    result = ProjectRunner(
        admin.memory,
        OpenCodeCoordinatorInvoker(workspace),
        notifier=OpenCodeUINotifier(workspace),
    ).run(args.assignment_id)
    return 1 if result == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
