"""Load sweep configuration through Hydra, without Hydra reaching further in.

Hydra is confined to composing sweep inputs.  It returns plain contracts, so nothing
downstream depends on OmegaConf types and the sweep runner is usable without Hydra at
all — which is what keeps this an entry-point dependency rather than a framework the
service layer is built on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import RankerVariant

DEFAULT_CONFIG_ROOT = Path(__file__).resolve().parents[2] / "configs" / "sweeps"


class HydraUnavailableError(RuntimeError):
    """Hydra is an optional extra; install it with `--extra sweeps`."""


def load_variants(names: list[str], *, config_root: Path | None = None) -> list[RankerVariant]:
    """Compose the named ranker configs into validated variants."""
    try:
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised by the extra's absence
        raise HydraUnavailableError(
            "Hydra is not installed; install the 'sweeps' extra to compose sweeps"
        ) from exc

    root = (config_root or DEFAULT_CONFIG_ROOT).resolve()
    variants: list[RankerVariant] = []
    with initialize_config_dir(config_dir=str(root), version_base=None):
        for name in names:
            composed = compose(config_name="config", overrides=[f"ranker={name}"])
            payload: Any = OmegaConf.to_container(composed.ranker, resolve=True)
            # Validated into a contract at the boundary: an unvalidated config object
            # would carry whatever the YAML happened to contain into the sweep.
            variants.append(RankerVariant.model_validate(payload))
    return variants
