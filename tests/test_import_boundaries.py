"""Regression tests for service package import boundaries."""


def test_tabular_handler_and_opt_in_registration_import_without_cycle() -> None:
    """The tabular handler must not be imported by the default tool inventory."""
    from services.tabular import run_tabular_baseline
    from services.tools import ToolContext, ToolRegistry, register_tabular_baseline

    registry = register_tabular_baseline(ToolRegistry())

    assert run_tabular_baseline is not None
    assert ToolContext is not None
    assert registry.get("train_tabular_baseline").handler is run_tabular_baseline
