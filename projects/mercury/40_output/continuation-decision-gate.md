# Continuation Decision Gate

## What happened

One authorized Kaggle CLI submission was made from the validated immutable seasonal-naive prediction artifact.

## External evaluation evidence

| Field | Value |
|---|---|
| Submission ID | `55488394` |
| Status | `complete` |
| Public score | `0.54320` |
| Private score | `not_available` |
| Local holdout RMSLE | `0.6489256798` |
| Artifact checksum | `123b37861cb4428df739965c1845f573fe7dc7e0e434f9e47403d9f950946466` |

The public Kaggle score is external benchmark evidence. It is not a production outcome, private score, leaderboard rank, or proof that the baseline is competitive.

## Recommendation

`continue_with_a_single_diagnostic_plan`

The local holdout and public score establish a valid reference, while the large last-observed fallback population remains an unresolved, evidence-backed limitation. Continue only with the already proposed aggregate error-analysis plan (`MERCURY-PLAN-0002`) to determine whether an improvement path is concentrated and testable.

An experiment-engineering outcome review confirms this recommendation. The local RMSLE and public Kaggle score are not directly comparable until evaluation definitions are independently verified. The public score is neither final private-benchmark evidence nor a production outcome.

## Not authorized by this decision

- Further Kaggle submissions
- Test prediction changes
- Feature/model changes
- Supplemental-source use
- Remote, external provider, or external-data use

Those actions each require their own plan and decision. The continuation recommendation is not an executable action.

## Outcome status

- Project outcome: `pending`
- Validation status: `partial` — one local baseline and one public external score exist.
- Production status: `not_deployed`

## Provenance

- Submission decision: `40_output/decisions/DEC-MERCURY-SUBMISSION-0001.yaml`
- External result: `30_evidence/mercury-seasonal-naive-submission-001-kaggle-result.json`
- Local run: `20_work/experiments/mercury-seasonal-naive-001/results.md`
