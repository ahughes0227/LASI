---
description: Validate a proposed dataset update and prepare governed comparison evidence.
agent: dataset-engineer
---

Use the implemented `lasi.datasets.service` functions `validate_dataset`, `characterize_dataset`, and `create_dataset_version` as applicable for `$ARGUMENTS`. Validate parent and proposed child manifests, preserve lineage and comparability, and prepare comparison evidence. Creating a dataset version or changing labels, benchmarks, privacy, or authoritative storage requires an approved `lasi.decisions.gate.DecisionGate` decision; do not execute those changes or bypass that gate.
