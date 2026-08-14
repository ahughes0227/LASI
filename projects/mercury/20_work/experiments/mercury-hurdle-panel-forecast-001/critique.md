# Novelty and critique

## Prior-attempt comparison

| Attempt | Signature | Comparable local RMSLE | Relationship |
|---|---|---:|---|
| `mercury-recursive-seasonal-001` | univariate recursive seven-day seasonal carry-forward | 0.6170404161 | narrow univariate reference; no learned conditional magnitude or zero process |
| `mercury-direct-gbdt-validation-001` | global direct multi-horizon `HistGradientBoostingRegressor` on a single sales target | 0.4609337296 | current best and primary divergence comparator |
| proposed | global direct-horizon two-part panel forecast: positivity probability plus conditional `log1p(sales)` magnitude | not_run | tests a different target-generating assumption while retaining the frozen evaluation protocol |

## Novelty score

Score: **0.75 / 1.00**, above the draft novelty floor of `0.60`.

- Target/objective structure: `0.30` — replaces one continuous target with a hurdle decomposition.
- Error-regime diagnosis: `0.20` — evaluates zero and positive sales separately; justified by 939,130 zero training targets.
- Model composition: `0.15` — two bounded estimators with probabilistic recombination rather than one regressor.
- Representation/assumptions: `0.10` — explicitly models occurrence and magnitude as distinct mechanisms.

Shared direct-horizon and frozen-split dimensions deliberately score `0.00`; they preserve comparability and do not inflate novelty. This is not a parameter retune. If rejected as insufficiently divergent during component review, it is `rejected_pre_execution` and consumes no plateau patience.

## Why this is the highest-information next branch

It isolates a visible distributional property—31.3% zero targets—at modest local cost and returns diagnostic bucket evidence even if global RMSLE does not improve. In contrast, adding unverified supplemental covariates would first require availability/lineage decisions, and another single-target GBDT configuration would be a near-duplicate.

## Existing capability status

- Existing compatible registered tool: `not_available`.
- Existing compatible registered component: `not_available`; current components are tabular classification only.
- `direct_horizon_gbdt:0.1.0` exists but is not a hurdle forecaster and its prior approval is scoped to that exact component. It cannot authorize this candidate.

## ComponentRequest (draft; no source or code has been created)

```yaml
request_id: CR-MERCURY-HURDLE-PANEL-FORECAST-001
project_id: mercury
requested_scope: project_experimental
component:
  component_id: mercury_hurdle_panel_forecaster
  name: Mercury direct-horizon hurdle panel forecaster
  version: 0.1.0
  lifecycle: draft
  description: >-
    A local, past-only forecasting component that fits a positive-sales classifier
    and conditional log1p-sales regressor for each direct horizon, recombines
    nonnegative expected sales, and emits lineage and zero/positive bucket metrics.
  inputs:
    - {name: train_panel_csv, artifact_type: protected_time_series_csv}
    - {name: frozen_temporal_split, artifact_type: temporal_split_definition}
  outputs:
    - {name: validation_predictions, artifact_type: forecasting_predictions}
    - {name: evaluation, artifact_type: forecasting_evaluation}
    - {name: feature_lineage, artifact_type: feature_lineage_audit}
  supported_modalities: [tabular_time_series]
  supported_problem_types: [forecasting]
  supported_execution_backends: [local]
  resource_requirements: {cost_usd: 0, cpu_hours: 0.25, wall_time_minutes: 20, memory_gb: 4, storage_gb: 0.5}
  known_limitations:
    - Does not establish official metric semantics; uses the frozen locally observed RMSLE convention.
    - Does not use supplemental tables until their temporal availability is separately established.
source_ref: not_created_research_only; required before review: project-scoped immutable source path
source_hash: not_available_no_source_created; required before review: sha256 of immutable source
dependencies: [numpy, pandas, scikit-learn]
test_refs:
  - required_before_review: synthetic_fixture_zero_and_positive_panel
  - required_before_review: synthetic_fixture_no_future_target_leakage
  - required_before_review: synthetic_fixture_nonnegative_recombination
  - required_before_review: synthetic_fixture_determinism_fixed_seed
expected_resource_use: {cost_usd: 0, cpu_hours: 0.25, wall_time_minutes: 20, memory_gb: 4, storage_gb: 0.5}
requires_network: false
requires_subprocess: false
requires_external_provider: false
requires_secrets: false
includes_native_code: false
writes_outside_workdir: false
mutates_shared_state: false
provenance:
  project_id: mercury
  source_records:
    - projects/mercury/30_evidence/mercury-direct-gbdt-validation-001-tool-run.json
    - projects/mercury/30_evidence/mercury-store-sales-v1-profile.json
    - projects/mercury/00_task/constraints.md
```

The request is intentionally not review-ready: a review requires immutable source, source hash, strict config schema, and passing synthetic tests. It is a requisition, not authorization to write code or execute it.
