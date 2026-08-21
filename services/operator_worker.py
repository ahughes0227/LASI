"""Minimal child-process entrypoint for one registered operator invocation."""

from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from .contracts import OperatorResult, StepStatus


def _resolve(entrypoint: str) -> Callable[[dict[str, Any], Path], Any]:
    module_name, separator, attribute_path = entrypoint.partition(":")
    if not separator:
        raise ValueError("entrypoint must use module:attribute syntax")
    value: Any = importlib.import_module(module_name)
    for part in attribute_path.split("."):
        value = getattr(value, part)
    if not callable(value):
        raise TypeError("operator entrypoint is not callable")
    return cast(Callable[[dict[str, Any], Path], Any], value)


def main() -> int:
    invocation_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    try:
        payload = json.loads(invocation_path.read_text())
        function = _resolve(payload["entrypoint"])
        returned = function(payload["arguments"], invocation_path.parent)
        if isinstance(returned, OperatorResult):
            result = returned
        else:
            result = OperatorResult(status=StepStatus.SUCCEEDED, outputs=returned or {})
    except BaseException as exc:
        result = OperatorResult(
            status=StepStatus.FAILED,
            failure_code="operator_exception",
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(result_path, flags, 0o600)
    with os.fdopen(descriptor, "w") as result_file:
        result_file.write(result.model_dump_json())
    return 0 if result.status == StepStatus.SUCCEEDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
