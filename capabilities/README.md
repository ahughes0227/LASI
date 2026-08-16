# Capability Packages

This directory holds fixed-shell capability packages created through
`/lasi-build-capability`. A package is not trusted or executable merely because
it exists here. Shared registration requires passing validation and an explicit
`update_toolbox` approval under the capability-development system.

Semantic operating descriptions remain under `system/capabilities/`; executable
bindings remain in the component and tool registries.

The current Glassy capability packages are:

| Package | Semantic source |
| --- | --- |
| `eda` | `system/capabilities/eda.md` |
| `research` | `system/capabilities/research.md` |
| `feature_engineering` | `system/capabilities/feature_engineering.md` |
| `modeling` | `system/capabilities/modeling.md` |
| `evaluation` | `system/capabilities/evaluation.md` |
| `critique` | `system/capabilities/critique.md` |
