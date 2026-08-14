# Experiment Results

Status: `succeeded`

## What happened

The approved local `seasonal_naive_baseline:v0.1.0` ran against the exact last-16-day chronological holdout, 2017-07-31 through 2017-08-15. It read only the approved `train.csv` workspace path and wrote only to the declared experiment artifact directory.

## What was produced

- `validation_predictions.csv` — 28,512 nonnegative validation predictions; SHA-256 `42ee1dc15fbfb26234d14c79a1e77b1b094671f58f7f4505ea312328dd05718a`
- `metrics.json` — SHA-256 `ebb8a5d10bf08577d41d4a9e0740f7d5cc7cba56e09165e01b963e5c4c466501`
- Structured tool result: `30_evidence/mercury-seasonal-naive-001-tool-run.json`

## Observed local validation metrics

| Metric | Value |
|---|---:|
| RMSLE | 0.6489256798 |
| MAE | 175.5726217528 |
| RMSE | 647.7324388007 |
| WAPE | 0.3758434583 |
| Evaluated rows | 28,512 |
| Seven-day seasonal lookups | 12,474 |
| Last-observed fallbacks | 16,038 |
| Cold-start zero fallbacks | 0 |
| Negative-prediction clipping | 0 |

## Interpretation limits

This is a single local reference result, not a Kaggle score, rank, production result, or evidence that the method is competitive. The high fallback count shows that a plain seven-day lookup is absent for many holdout rows; this is evidence for a planned feature/seasonality investigation, not authorization to add features.

## Provenance

- Dataset: `mercury-store-sales:v1`
- Plan: `MERCURY-PLAN-0001`
- Decision: `DEC-MERCURY-BASELINE-0001`
- Tool: `seasonal_naive_baseline:v0.1.0`
- Backend: local
- Isolation profile: `mercury-seasonal-naive-local-v1`
- Artifact inventory: `30_evidence/mercury-seasonal-naive-001-artifact-inventory.json`
