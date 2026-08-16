"""Discovery and preflight for the OpenCode CLI the runtime shells out to.

Every agent turn is an `opencode run` child process, so a missing or unusable
CLI is an infrastructure fault rather than a research failure.  Checking it
before an assignment changes state keeps that fault from being recorded as a
run of exhausted agent retries.
"""

from __future__ import annotations

import os
import shutil
import subprocess


class OpenCodeRuntimeError(RuntimeError):
    """Non-retryable local infrastructure failure before an agent turn."""


def resolve_opencode_executable(executable: str | None = None) -> str:
    configured = executable or os.environ.get("LASI_OPENCODE_EXECUTABLE", "opencode")
    resolved = shutil.which(configured)
    if resolved is None:
        raise OpenCodeRuntimeError(
            f"OpenCode CLI is unavailable: {configured!r} was not found on PATH"
        )
    return resolved


def validate_opencode_runtime(executable: str | None = None) -> str:
    """Verify the CLI and its non-interactive run command before launching work."""
    resolved = resolve_opencode_executable(executable)
    try:
        completed = subprocess.run(  # noqa: S603 - resolved executable, no shell.
            [resolved, "run", "--help"],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OpenCodeRuntimeError(f"OpenCode CLI preflight failed: {exc}") from exc
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode != 0 or "opencode run" not in output.lower():
        detail = output.strip()[-1000:]
        raise OpenCodeRuntimeError(
            f"OpenCode CLI does not provide an operational run command: {detail}"
        )
    return resolved


__all__ = [
    "OpenCodeRuntimeError",
    "resolve_opencode_executable",
    "validate_opencode_runtime",
]
