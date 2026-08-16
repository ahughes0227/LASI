"""Non-network transports used to exercise the SSH execution boundary."""

import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from services.core import COMPONENT_ENVIRONMENT_ALLOWLIST, build_child_environment

from .models import EnvironmentCheck, TransportResult


class RemoteTransport(Protocol):
    """Transport operations required by the remote runner."""

    def prepare_workspace(self, workspace: str) -> None: ...

    def check_environment(
        self, workspace: str, python_command: str, setup_command: str | None
    ) -> list[EnvironmentCheck]: ...

    def stage(self, source: Path, workspace: str, relative_path: str) -> None: ...

    def execute(
        self,
        command: str,
        workspace: str,
        timeout_seconds: float,
    ) -> TransportResult: ...

    def retrieve(self, workspace: str, relative_path: str, destination: Path) -> None: ...

    def cleanup(self, workspace: str) -> None: ...


class MockTransport:
    """Scriptable transport that never executes a process or contacts a host."""

    def __init__(
        self,
        root: Path,
        *,
        result: TransportResult | None = None,
        checks: list[EnvironmentCheck] | None = None,
        on_execute: Callable[[str, Path], None] | None = None,
    ) -> None:
        self.root = root
        self.result = result or TransportResult(0)
        self.checks = checks or [EnvironmentCheck("connectivity", True, "mock transport")]
        self.on_execute = on_execute
        self.commands: list[str] = []

    def _path(self, workspace: str, relative: str = "") -> Path:
        prefix = "/" if workspace.startswith("/") else ""
        path = (self.root / workspace.lstrip(prefix)).joinpath(relative)
        resolved = path.resolve()
        if self.root.resolve() not in resolved.parents and resolved != self.root.resolve():
            raise ValueError("remote path escapes transport root")
        return resolved

    def prepare_workspace(self, workspace: str) -> None:
        self._path(workspace).mkdir(parents=True, exist_ok=True)

    def check_environment(
        self, workspace: str, python_command: str, setup_command: str | None
    ) -> list[EnvironmentCheck]:
        return list(self.checks)

    def stage(self, source: Path, workspace: str, relative_path: str) -> None:
        destination = self._path(workspace, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def execute(
        self,
        command: str,
        workspace: str,
        timeout_seconds: float,
    ) -> TransportResult:
        self.commands.append(command)
        if self.on_execute is not None:
            self.on_execute(command, self._path(workspace))
        return self.result

    def retrieve(self, workspace: str, relative_path: str, destination: Path) -> None:
        source = self._path(workspace, relative_path)
        if not source.is_file():
            raise FileNotFoundError(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def cleanup(self, workspace: str) -> None:
        shutil.rmtree(self._path(workspace))


class LoopbackTransport(MockTransport):
    """Runs commands in a local sandbox, never through SSH."""

    _ALLOWED_EXECUTABLES = {"echo", "python", "python3", Path(sys.executable).name.lower()}

    @classmethod
    def _argv(cls, command: str) -> list[str]:
        """Parse a command without giving it shell syntax or shell expansion."""
        if any(character in command for character in ";|&<>$`\r\n"):
            raise ValueError("loopback command contains shell syntax")
        argv = shlex.split(command, posix=True)
        if not argv:
            raise ValueError("loopback command is empty")
        executable = Path(argv[0]).name.lower()
        if executable not in cls._ALLOWED_EXECUTABLES:
            raise ValueError(f"loopback executable is not allowed: {executable}")
        return argv

    def execute(
        self,
        command: str,
        workspace: str,
        timeout_seconds: float,
    ) -> TransportResult:
        self.commands.append(command)
        try:
            argv = self._argv(command)
            completed = subprocess.run(
                argv,
                cwd=self._path(workspace),
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env=build_child_environment(COMPONENT_ENVIRONMENT_ALLOWLIST),
            )
        except subprocess.TimeoutExpired as exc:
            return TransportResult(-1, str(exc.stdout or ""), str(exc.stderr or ""), True)
        return TransportResult(completed.returncode, completed.stdout, completed.stderr)
