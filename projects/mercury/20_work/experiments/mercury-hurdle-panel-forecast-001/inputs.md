# Declared inputs

## Immutable benchmark inputs (read-only)

- Dataset version: `mercury-store-sales:v1`
- Official local input root: `projects/mercury/artifacts/challenge-9d7fee07ed6b480eba619bfd913a11fe/input/`
- Required files: `train.csv`; `test.csv` only if a later separately authorized forecast artifact is requested.
- Panel keys: `store_nbr`, `family`; time key: `date`; target: `sales`.

No hidden labels, external data, network resources, remote execution, external providers, arbitrary subprocesses, or mutable dataset paths are inputs.

## Evidence inputs

- `30_evidence/mercury-direct-gbdt-validation-001-tool-run.json`
- `30_evidence/mercury-recursive-seasonal-001-tool-run.json`
- `30_evidence/mercury-store-sales-v1-profile.json`
- `30_evidence/mercury-store-sales-v1-time-aware-audit.json`
- `30_evidence/mercury-challenge-spec.json`
- `00_task/constraints.md`
- `40_output/divergence-policy.md`

## Frozen comparability contract

Fit rows end on `2017-07-30`; validate only dates `2017-07-31` through `2017-08-15` (16 dates; 28,512 rows). Use `mercury-store-sales:v1`, RMSLE with predictions clipped at zero, fixed seed `20260813`, and no validation target in feature construction. This is directly comparable to `mercury-direct-gbdt-validation-001` only under this unchanged contract.
