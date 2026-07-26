---
name: challenge-intake
description: Use for locally supplied Kaggle-style challenge intake, file inventory, hashing, schema confirmation, and benchmark-isolation setup.
---

# Challenge intake

1. Treat the brief and files as novel local evidence. Never infer answers from challenge names.
2. Create a `ChallengeSpec` with unknowns made explicit; consequential target, ID, split, metric, and submission assumptions require user confirmation.
3. Inventory only supplied files inside the challenge workspace and record immutable SHA-256 hashes.
4. Use registered non-executable format adapters. Reject unsafe serialization, ambiguous formats, archive traversal, and unsupported formats with structured reasons.
5. Run leakage audit before characterization. Findings never mutate labels, splits, or benchmarks.
6. Enable benchmark isolation: no network, external provider, remote execution, arbitrary subprocess, or external data unless a separate governed decision permits it.
7. Handoff a typed challenge specification, file inventory, hashes, audit, and workspace paths to dataset characterization; do not create a dataset version or execute a model from this procedure alone.
