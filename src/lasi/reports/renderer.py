"""Render the canonical report contract as an immutable static HTML artifact."""

from collections.abc import Mapping
from pathlib import Path
from shutil import copyfile
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from lasi.contracts import StaticReportData, validate_contract

_TEMPLATE_DIR = Path(__file__).with_name("templates")


class ImmutableReportError(FileExistsError):
    """Raised when a report artifact would overwrite an existing artifact."""


class ReportRenderer:
    """Render `StaticReportData` through the fixed report template."""

    def __init__(self, template_dir: Path | None = None) -> None:
        directory = template_dir or _TEMPLATE_DIR
        self._environment = Environment(
            loader=FileSystemLoader(directory),
            autoescape=select_autoescape(["html", "xml"], default=True),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, data: StaticReportData | Mapping[str, Any]) -> str:
        """Validate and render a report without consulting external state."""

        report = (
            data
            if isinstance(data, StaticReportData)
            else validate_contract(StaticReportData, data)
        )
        return self._environment.get_template("report.html.j2").render(report=report)

    def write_immutable(
        self, data: StaticReportData | Mapping[str, Any], output_path: str | Path
    ) -> Path:
        """Write an HTML report once, preserving reviewed artifacts from overwrite."""

        path = Path(output_path)
        if path.exists():
            raise ImmutableReportError(f"Refusing to overwrite report artifact: {path}")
        stylesheet = path.with_name("style.css")
        if stylesheet.exists():
            raise ImmutableReportError(f"Refusing to overwrite report asset: {stylesheet}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(data), encoding="utf-8", newline="\n")
        copyfile(_TEMPLATE_DIR / "style.css", stylesheet)
        return path


def render_report(data: StaticReportData | Mapping[str, Any]) -> str:
    """Render a validated `StaticReportData` instance with the default template."""

    return ReportRenderer().render(data)
