Projects Folder
===============

Create project folders here following the pattern `projects/<project-id>/` with an `artifacts/` subfolder.

Example layout:

- projects/my-dataset-diagnostic/
  - artifacts/
  - context.md
# Project ICM

Each substantial project has an isolated semantic workspace under
`projects/<project_id>/`:

```text
00_task/  10_context/  20_work/  30_evidence/  40_output/
```

This workspace stores human- and LLM-readable task state, work artifacts,
evidence, failures, and handoffs. SQL, MLflow, telemetry, and other structured
systems remain authoritative for machine-native state.
