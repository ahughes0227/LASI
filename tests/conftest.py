"""Shared pytest configuration for LASI tests."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))


def pytest_configure(config: object) -> None:
    """Register the marker so `--strict-markers` accepts it."""
    config.addinivalue_line(  # type: ignore[attr-defined]
        "markers",
        "postgres: exercises behaviour SQLite cannot express; needs LASI_TEST_DATABASE_URL",
    )
    config.addinivalue_line(  # type: ignore[attr-defined]
        "markers",
        "dspy: needs the optional 'dspy' extra installed",
    )
