import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel
from services.components import (
    DEFAULT_COMPONENT_TIMEOUT_SECONDS,
    ComponentRunOutput,
    SubprocessBinding,
)
from services.components.execution import ComponentExecutionContext


class EmptyConfig(BaseModel):
    pass


def test_subprocess_binding_uses_registered_command_and_artifact_paths(tmp_path: Path) -> None:
    script = tmp_path / "component.py"
    script.write_text(
        "import json, sys\n"
        "invocation = json.load(open(sys.argv[1]))\n"
        "json.dump({'outputs': {'result': 'result.txt'}}, open(invocation['result_path'], 'w'))\n"
        "open('result.txt', 'w').write('ok')\n",
        encoding="utf-8",
    )
    binding = SubprocessBinding((sys.executable, str(script)))
    context = ComponentExecutionContext(
        project_id="project",
        dataset_version_id="dataset",
        experiment_spec_id="spec",
        node_id="node",
        workdir=tmp_path,
        inputs={},
        config=EmptyConfig(),
        random_seed=None,
    )

    output = binding(context)

    assert isinstance(output, ComponentRunOutput)
    assert output.outputs["result"].read_text() == "ok"


def test_binding_always_carries_a_wall_clock_bound() -> None:
    """An unbounded command holds its worker until the process is killed by hand."""
    assert SubprocessBinding(("true",)).timeout_seconds == DEFAULT_COMPONENT_TIMEOUT_SECONDS


@pytest.mark.parametrize("unbounded", [0, -1])
def test_binding_refuses_a_non_positive_timeout(unbounded: float) -> None:
    with pytest.raises(ValueError, match="positive wall-clock bound"):
        SubprocessBinding(("true",), timeout_seconds=unbounded)


def test_binding_enforces_its_timeout_on_a_hanging_command(tmp_path: Path) -> None:
    script = tmp_path / "hang.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    binding = SubprocessBinding((sys.executable, str(script)), timeout_seconds=0.5)
    context = ComponentExecutionContext(
        project_id="project",
        dataset_version_id="dataset",
        experiment_spec_id="spec",
        node_id="node",
        workdir=tmp_path,
        inputs={},
        config=EmptyConfig(),
        random_seed=None,
    )

    with pytest.raises(subprocess.TimeoutExpired):
        binding(context)
