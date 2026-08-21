"""Small deterministic operators used for health checks and core verification."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


def echo(arguments: dict[str, Any], workspace: Path) -> dict[str, Any]:
    return {"echo": arguments}


def environment(arguments: dict[str, Any], workspace: Path) -> dict[str, Any]:
    return {"present": sorted(key for key in arguments["keys"] if key in os.environ)}


def sleep(arguments: dict[str, Any], workspace: Path) -> dict[str, Any]:
    time.sleep(float(arguments["seconds"]))
    return {"slept": arguments["seconds"]}


def write_artifact(arguments: dict[str, Any], workspace: Path) -> dict[str, Any]:
    path = workspace / "artifact.txt"
    path.write_text(str(arguments["content"]))
    return {"artifact_paths": [str(path)]}


def write_symlink_artifact(arguments: dict[str, Any], workspace: Path) -> dict[str, Any]:
    target = workspace / "target.txt"
    target.write_text(str(arguments["content"]))
    link = workspace / "artifact-link.txt"
    link.symlink_to(target)
    return {"artifact_paths": [str(link)]}


def hard_exit(arguments: dict[str, Any], workspace: Path) -> dict[str, Any]:
    os._exit(int(arguments.get("code", 7)))
