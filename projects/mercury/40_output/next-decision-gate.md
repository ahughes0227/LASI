# Next Decision Gate

## Current evidence

The approved seasonal-naive baseline completed with local holdout RMSLE `0.6489256798`. This is an observed local validation result only.

## Recommended next action

Draft a single controlled, past-only calendar-and-lag baseline plan, then submit it for a separate decision. It should compare directly with the completed baseline using the same dataset version, 2017-07-31 through 2017-08-15 holdout, RMSLE/minimize metric, local-only backend, and benchmark isolation profile.

## Why

The baseline used last-observed fallback for 16,038 of 28,512 rows. That finding supports testing a carefully specified past-only feature policy, but does not by itself justify arbitrary feature work, supplemental-source use, model scaling, prediction generation, or a Kaggle submission.

## Still not authorized

- Any Kaggle test prediction or submission
- Supplemental tables (`transactions`, `oil`, holidays) as features
- Remote execution, external data, external providers, or network access
- Dataset/benchmark modifications
- An experiment without a separately approved plan and registered tool

## Required next inputs

1. A bounded plan and trusted registered local tool for calendar/lag features.
2. A feature-lineage audit proving every derived feature uses only data before each forecast date.
3. A plan-specific decision record.

## Provenance

- `20_work/experiments/mercury-seasonal-naive-001/results.md`
- `30_evidence/mercury-seasonal-naive-001-tool-run.json`
- `30_evidence/mercury-seasonal-naive-001-artifact-inventory.json`

## Experiment evidence review

An experiment-engineering review found the baseline evidence sufficient as a leakage-controlled local reference under its approved scope. It confirmed no Kaggle prediction artifact, score, rank, or submission occurred.

The review recommends only a future non-executable aggregate error-analysis plan (`MERCURY-PLAN-0002` proposed): compare the seasonal-lookup and last-observed-fallback strata using the existing holdout predictions and labels. This requires a new trusted diagnostic tool and a separate decision; it is not authorized by this review.
