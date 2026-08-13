# Direct GBDT Outcome

## What happened

The accepted divergent direct multi-horizon GBDT branch was run on the frozen local holdout and then submitted once after schema/ID validation.

## Results

| Evidence | Seasonal recursive | Direct GBDT | Change |
|---|---:|---:|---:|
| Local RMSLE | 0.6170404161 | 0.4609337296 | -0.1561066865 |
| Kaggle public score | 0.52245 | 0.49942 | -0.02303 |

Submission ID: `55489163`. Private score: `not_available`.

## Interpretation

This is a meaningful improvement across a materially divergent model family. It supports continued research, not a production claim or a conclusion that this is near-optimal. Two daily submissions remain. The next branch must remain sufficiently novel: incorporate permitted static store attributes and known-future holiday policy only after a separate availability/leakage audit, or pursue a hierarchical/latent-factor family.

## Provenance

- Local result: `30_evidence/mercury-direct-gbdt-validation-001-tool-run.json`
- Submission: `30_evidence/mercury-direct-gbdt-submission-001-submission-record.json`
