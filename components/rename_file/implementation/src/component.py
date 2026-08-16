import shutil
from pathlib import Path

from pydantic import BaseModel, Field
from services.components.execution import ComponentExecutionContext, ComponentRunOutput


class RenameFileConfig(BaseModel):
    destination_name: str = Field(min_length=1)
    overwrite_policy: str = "fail"


def handler(context: ComponentExecutionContext) -> ComponentRunOutput:
    config = RenameFileConfig.model_validate(context.config)
    if config.overwrite_policy not in {"fail", "replace"}:
        raise ValueError("overwrite_policy must be fail or replace")
    if Path(config.destination_name).name != config.destination_name:
        raise ValueError("destination_name must be a file name")
    destination = context.workdir / config.destination_name
    if destination.exists() and config.overwrite_policy == "fail":
        raise FileExistsError(destination)
    shutil.copy2(context.inputs["source"], destination)
    return ComponentRunOutput(outputs={"renamed_file": destination})
