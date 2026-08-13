# Toolbox Acceptance — Seasonal-Naive Baseline v0.1.0

## Status

`accepted_for_registered_local_use`

The project owner authorized the scoped toolbox update in `APP-MERCURY-TOOLBOX-SEASONAL-NAIVE-0001`. The trusted local tool is accepted for registry promotion only. This does not authorize a Mercury experiment, forecast, local metric calculation, prediction artifact, Kaggle submission, network access, remote execution, external provider use, or dataset change.

## Produced toolbox capability

- Tool ID/version: `seasonal_naive_baseline` / `0.1.0`
- Implementation: `services/timeseries/seasonal_naive.py`
- Registration: `services.tools.register_seasonal_naive_baseline`
- Scope: local-only, tabular time-series forecasting, seasonal-naive reference baseline
- Required registration authorization: matching non-expired `update_toolbox` approval ID, project ID, and proposal ID.

## Accepted safety constraints

- Opt-in registration only; no default tool inventory change.
- Mandatory protected benchmark mode and deny-all profile for the handler.
- Read and write paths must be explicitly allowlisted.
- Train panel must have unique `(date, store_nbr, family)` rows, finite nonnegative sales, and valid dates.
- Forecast history is fixed strictly before the holdout; holdout labels never update history.
- Outputs are finite, nonnegative validation predictions and structured metrics artifacts.

## Verification evidence

- Synthetic acceptance tests: `tests/test_seasonal_naive.py`
- Related registry/isolation tests: `tests/test_tools.py`; `tests/test_benchmark_harness.py`; `tests/test_import_boundaries.py`; `tests/test_mercury_records.py`
- Verification result: `19 passed`
- Ruff result: passed for the changed toolbox paths

## Known limitations and next decision gate

- Isolation enforcement is constrained to the trusted handler’s declared paths and policy preflight; an OS sandbox remains required before hostile or third-party code can be considered.
- The official Mercury metric and detailed rules remain `not_locally_verified`.
- Error buckets, supplemental features, and hidden-label evaluation are not part of this tool.
- Registering the tool does not run it. `MERCURY-PLAN-0001` still requires a plan-specific decision with a verified metric, fixed holdout, exact parameters, and an isolation profile before execution.

## Artifact contract

- **READ:** toolbox proposal, approval, source implementation, and synthetic acceptance evidence.
- **DO:** promote this exact trusted local implementation to the explicit registry.
- **WRITE:** this acceptance record and future registry-use/tool-run evidence.

## Provenance

- Proposal: `40_output/toolbox-proposal-seasonal-naive.yaml`
- Approval: `40_output/approvals/APP-MERCURY-TOOLBOX-SEASONAL-NAIVE-0001.yaml`
- User authorization: 2026-08-13
