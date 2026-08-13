# Local Challenge Intake — Mercury

## Status

`superseded_by_version_and_characterization`

## What happened

The scoped Kaggle CLI acquisition retrieved the official archive. A safe archive extraction and read-only challenge-workspace intake copied the seven CSV assets into `artifacts/challenge-9d7fee07ed6b480eba619bfd913a11fe/input/`, made the copies read-only, and computed SHA-256 checksums. CSV schema inspection completed without executing source content.

No raw data, labels, canonical dataset version, benchmark definition, privacy policy, or authoritative storage was modified. No model, feature engineering, validation, prediction, or submission was run.

## Local file inventory

| File | Bytes | SHA-256 | Columns |
|---|---:|---|---|
| `train.csv` | 121800373 | `99a1b7f4241821df10fa71f23abdd71c634f71f901e3cab1400c0f0c583f862c` | `id,date,store_nbr,family,sales,onpromotion` |
| `test.csv` | 1022269 | `087ec1ecec76dbba9ea2adb48b8b2fd527c7c59adb82b0dfb9f6f82739400d26` | `id,date,store_nbr,family,onpromotion` |
| `sample_submission.csv` | 342153 | `17505ec561d9bc64a3c10c3eb00474becf162d9053cebf014a58a6c82ed530c4` | `id,sales` |
| `stores.csv` | 1387 | `af503b2bce11d7906d249f81cc0598f10e2addcc9f6c59aa2d95c9f2652c296b` | `store_nbr,city,state,type,cluster` |
| `oil.csv` | 20580 | `944b23b857580f9d804399346fd3ed69bffcb7facfd98c55fdb408b8d057cca7` | `date,dcoilwtico` |
| `holidays_events.csv` | 22309 | `81a183d6c4d691b57f84a0fde6bbf734a5b3c36a74b97378bf33a592648e2999` | `date,type,locale,locale_name,description,transferred` |
| `transactions.csv` | 1552637 | `e116384a6981af74932832436aa2f6a43121f77ca81accc44e3a5160158ca03c` | `date,store_nbr,transactions` |

All files were accepted by the registered CSV format adapter (`1.0`).

## Challenge specification proposal

| Field | Proposed value | State |
|---|---|---|
| Challenge ID | `store-sales-time-series-forecasting` | `observed_from_cli_request` |
| Project ID | `mercury` | `observed` |
| Problem type | temporal-panel regression / forecasting | `inferred_from_local_schema` |
| Train source | `input/train.csv` | `observed` |
| Test source | `input/test.csv` | `observed` |
| Supplemental sources | five remaining CSV assets | `observed` |
| Target | `sales` | `observed_train_only` |
| Identifier | `id` | `observed_submission_schema` |
| Time field | `date` | `observed` |
| Candidate panel grain | `(date, store_nbr, family)` | `requires_uniqueness_audit` |
| Prediction field | `sales` | `observed_submission_schema` |
| Metric and direction | `not_locally_verified` | public metadata reports RMSLE/minimize, but local rules did not confirm it |
| Forecast horizon, rules, and submission limit | unknown | `requires_rule_confirmation` |
| Privacy mode | local-only | `active_project_constraint` |
| External data | denied | `active_project_constraint` |
| Network after intake | denied except a separately approved submission | `active_project_constraint` |

## Leakage-audit status

`not_run` — a time-aware audit is required before characterization and any plan. The generic duplicate-feature audit is not suitable as a leakage conclusion for a temporal panel: repeated predictor patterns across dates are expected, while leakage can arise from future-derived lags, aggregates, encodings, or temporally misaligned joins.

The audit must establish chronological validation folds, key uniqueness, target availability, and past-only construction for every feature. `transactions`, `oil`, and holiday data are not approved features until their availability timing and join behavior are audited.

## Historical approval gate

At creation, this intake record required initial-import approval. The project owner later approved the exact seven hashed inputs in `40_output/approvals/APP-MERCURY-INITIAL-IMPORT-0001.yaml`. Dataset version `mercury-store-sales:v1` was created, the time-aware audit completed, and characterization completed. Current state is in `10_context/current_state.md`; current characterization is in `10_context/dataset_characterization.md`.

## Artifact contract

- **READ:** read-only workspace inputs, CLI acquisition record, and hash records.
- **DO:** retain safe file inventory, format inspection, and schema-confirmation evidence; do not authorize current work.
- **WRITE:** none. Follow-on version and audit records are the durable successor artifacts.

## Provenance

- User scoped authorization: 2026-08-13
- Kaggle CLI: `2.2.4`
- Source artifacts: `40_output/kaggle-cli-authorization.md`; `30_evidence/task-ledger.md`
- Challenge workspace: `artifacts/challenge-9d7fee07ed6b480eba619bfd913a11fe/`
