# Dataset Characterization — Mercury Store Sales v1

## Status and identity

- Project ID: `mercury`
- Dataset ID: `mercury-store-sales`
- Dataset version: `mercury-store-sales:v1`
- Version status: `characterized`
- Dataset role: `training_and_hidden_challenge_test`
- Dataset changes: `initial_import` only; labels, splits, benchmark definition, and source files were not changed.

## Sample and panel summary

| Measure | Observed value |
|---|---:|
| Training rows | 3,000,888 |
| Test rows | 28,512 |
| Training date range | 2013-01-01 to 2017-08-15 |
| Test date range | 2017-08-16 to 2017-08-31 |
| Training dates | 1,684 |
| Test forecast dates | 16 |
| Stores | 54 |
| Product families | 33 |
| Panel entities (`store_nbr`, `family`) | 1,782 |
| Expected full-panel rows per date | 1,782 |
| Submission rows | 28,512 |

The test dates are strictly after the last training date, with no overlap. Both train and test have zero duplicate `(date, store_nbr, family)` keys. Test has a full 1,782-row panel per date and exactly the same store/family coverage as train.

## Target and missingness

`sales` is present in train only; it ranges from 0 to 124,717 with mean 357.776. There are 939,130 zero-sales rows (31.29%) and no negative values. Train and test core fields have no missing values.

Supplemental gaps: `oil.dcoilwtico` has 43 missing values. `holidays_events` has 350 rows and 38 duplicate dates, so it requires an intentional aggregation/join policy. Training omits four calendar dates (each December 25); this is an observed calendar gap, not a source-data correction proposal.

## Time-aware quality and leakage audit

Status: `partial_success`.

Completed evidence:

- Train/test temporal boundary is clean (`2017-08-15` → `2017-08-16`).
- The target does not occur in test.
- Candidate panel keys are unique in train and test.
- Store and family coverage are unchanged across train and test.

Explicit unresolved states:

- Feature-lineage audit for lags, rolling statistics, target encodings, and aggregates: `not_run_no_derived_features`.
- Holiday, oil, and transaction availability at forecast time: `not_available_requires_rule_or_domain_confirmation`.
- Oil imputation and holiday aggregation: `not_run`.
- `transactions` as a feature: `not_approved_as_feature_pending_availability_assessment`.

## Highest-priority issues

1. **Temporal validation policy and official metric are not yet fixed** — random splits would be invalid. Use an approved chronological holdout or rolling-origin folds with all feature transforms rebuilt inside each fold; do not treat the public RMSLE report as a verified contract.
2. **Target zero inflation and scale** — 31.29% of sales values are zero and the maximum is 124,717. A baseline must use nonnegative predictions and an RMSLE-compatible target/prediction treatment.
3. **Supplemental temporal availability is unresolved** — do not use transactions, oil imputation, or holiday/event joins until the feature availability and leakage policy is explicitly tested and documented.
4. **Holiday table is not one row per date** — joining directly would expand panel rows. Aggregate deliberately by date and locale relevance only after approval in a planned experiment.
5. **Observed Christmas gaps** — calendar continuity assumptions must distinguish source omissions from zero sales; do not silently fill source labels.

## Recommended controlled experiments

1. A local, chronological, no-supplemental naive seasonal baseline to validate split construction and RMSLE implementation.
2. A directly comparable baseline that adds only past-derived lags/calendar features, with fold-local construction and no supplemental tables.
3. Only after error analysis and availability review: a single supplemental-feature ablation for safely available holiday features; transactions and oil remain excluded pending their availability audit.

## Summary table

| Profile | Status | Key finding | Evidence |
|---|---|---|---|
| Primitive | complete | Daily 54×33 panel | profile JSON |
| Distribution | complete | Zero-inflated, right-skewed target | profile JSON |
| Quality | partial_success | Core fields complete; oil gaps and holiday duplicate dates | profile JSON |
| Coverage | complete | Train/test store-family coverage matches | profile and audit JSON |
| Leakage | partial_success | Clean raw temporal boundary; derived-feature availability untested | audit JSON |

## Provenance

- Manifest: `30_evidence/mercury-store-sales-v1-manifest.json`
- Dataset version: `30_evidence/mercury-store-sales-v1-dataset-version.json`
- Profile: `30_evidence/mercury-store-sales-v1-profile.json`
- Time-aware audit: `30_evidence/mercury-store-sales-v1-time-aware-audit.json`
- Approval: `40_output/approvals/APP-MERCURY-INITIAL-IMPORT-0001.yaml`
