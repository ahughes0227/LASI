# Mercury Task and Usage Ledger

## Purpose

Readable append-only project-ICM task ledger. SQLite operational memory and authoritative runtime receipts remain machine-native sources of truth when provisioned; this file records durable handoffs and explicit coverage states.

## Status and domains

Task status: `planned`, `succeeded`, `failed`, or `blocked`. Each task has one primary domain: `challenge_intake`, `dataset`, `experiment`, `scientist_review`, `decision_governance`, `reporting`, `outcome`, `knowledge`, `harness_maintenance`, or `operations`.

Usage metering status: `reported` only with an authoritative receipt; otherwise `not_applicable` for non-token actions or `not_available` when the runtime omits a receipt. No token or cost estimate is inferred.

| event_id | task_id | domain | task_name | status | execution_status | success criteria | reason / evidence refs |
|---|---|---|---|---|---|---|---|
| `mercury-task-0001` | `mercury-challenge-intake` | `challenge_intake` | Initial challenge intake handoff | `blocked` | `not_started` | Local official files available for governed intake. | Missing local inputs. `10_context/challenge_intake_handoff.md`; `30_evidence/failures/INTAKE-MERCURY-0001.md` |
| `mercury-task-0002` | `mercury-kaggle-cli-acquisition` | `operations` | Kaggle CLI availability and official asset acquisition | `succeeded` | `completed` | CLI availability/authentication checked and official challenge archive retrieved. | CLI `2.2.4`; `kaggle competitions files` returned the seven official files; archive at `artifacts/kaggle-download/store-sales-time-series-forecasting.zip`. Hash/intake remains pending. Scoped authorization: `40_output/kaggle-cli-authorization.md` |
| `mercury-task-0003` | `mercury-local-intake` | `challenge_intake` | Hash, safe extraction, read-only workspace intake, and schema inspection | `succeeded` | `completed` | Official files copied into protected workspace with SHA-256 inventory and schema inspection. | `10_context/local-intake.md` |
| `mercury-task-0004` | `mercury-initial-import-approval` | `decision_governance` | Approve initial immutable dataset version | `succeeded` | `completed` | Explicit approval decision is recorded. | `40_output/approvals/APP-MERCURY-INITIAL-IMPORT-0001.yaml` |
| `mercury-task-0005` | `mercury-initial-import-decision-review` | `decision_governance` | Review and approve initial-import authorization | `succeeded` | `completed` | Governance review and subsequent explicit owner approval record whether characterization may proceed. | Final scoped outcome `allow_with_warning`; `40_output/initial-import-decision-gate.md`; `40_output/approvals/APP-MERCURY-INITIAL-IMPORT-0001.yaml` |
| `mercury-task-0006` | `mercury-initial-import-version` | `dataset` | Create immutable initial dataset version | `succeeded` | `completed` | Initial-import version preserves approved input hashes and lineage. | `30_evidence/mercury-store-sales-v1-dataset-version.json`; approval `APP-MERCURY-INITIAL-IMPORT-0001` |
| `mercury-task-0007` | `mercury-time-series-characterization` | `dataset` | Time-aware leakage audit and characterization | `succeeded` | `completed` | Panel schema, coverage, target distribution, missingness, and explicit unresolved leakage states recorded. | `10_context/dataset_characterization.md`; `30_evidence/mercury-store-sales-v1-profile.json`; `30_evidence/mercury-store-sales-v1-time-aware-audit.json` |
| `mercury-task-0008` | `mercury-baseline-plan` | `experiment` | Compile chronological seasonal-naive baseline plan | `succeeded` | `completed` | Non-executable plan defines split, artifacts, success/failure conditions, and tool availability state. | `20_work/experiment-plan-0001.md` |
| `mercury-task-0009` | `mercury-baseline-plan-decision` | `decision_governance` | Authorize or block baseline plan | `blocked` | `not_started` | A decision evaluates the plan, tool availability, temporal policy, and confirmed metric. | Required before execution; time-series tools and a locally verified official metric are `not_available`. |
| `mercury-task-0010` | `mercury-toolbox-seasonal-naive` | `harness_maintenance` | Build and accept trusted seasonal-naive baseline toolbox capability | `succeeded` | `completed` | Scoped tool registration, synthetic safety tests, and code review evidence complete; no challenge data executed. | `40_output/toolbox-acceptance-seasonal-naive.md` |
| `mercury-task-0011` | `mercury-seasonal-naive-baseline` | `experiment` | Run approved local seasonal-naive chronological baseline | `succeeded` | `completed` | Required artifacts and finite nonnegative predictions produced under the approved isolation profile. | `20_work/experiments/mercury-seasonal-naive-001/results.md`; `30_evidence/mercury-seasonal-naive-001-tool-run.json` |
| `mercury-task-0012` | `mercury-seasonal-naive-test-forecast` | `experiment` | Generate and validate protected seasonal-naive test prediction artifact | `succeeded` | `completed` | One id,sales prediction per test row passed ID/schema validation. | `30_evidence/mercury-seasonal-naive-submission-001-prediction-artifact.json`; `30_evidence/mercury-seasonal-naive-submission-001-validation.json` |
| `mercury-task-0013` | `mercury-kaggle-submission-001` | `operations` | Submit one validated seasonal-naive artifact with Kaggle CLI | `succeeded` | `completed` | Kaggle CLI accepted one submission and external result was recorded. | Submission `55488394`; `30_evidence/mercury-seasonal-naive-submission-001-kaggle-result.json` |
| `mercury-task-0014` | `mercury-continuation-review-001` | `decision_governance` | Interpret one external score for continuation | `succeeded` | `completed` | Continuation recommendation distinguishes evidence from authorization. | `40_output/continuation-decision-gate.md` |
| `mercury-task-0015` | `mercury-recursive-seasonal-comparison` | `experiment` | Compare leakage-free recursive seasonal baseline | `succeeded` | `completed` | Same-split local RMSLE improved to 0.6170404161 with no fallback observations. | `30_evidence/mercury-recursive-seasonal-001-tool-run.json` |
| `mercury-task-0016` | `mercury-recursive-kaggle-submission` | `operations` | Submit recursive seasonal-naive candidate | `succeeded` | `completed` | Kaggle public score improved from 0.54320 to 0.52245. | Submission `55488565`; `30_evidence/mercury-recursive-seasonal-submission-001-kaggle-result.json` |
| `mercury-task-0017` | `mercury-divergence-research-policy` | `decision_governance` | Record divergence-first research escalation | `succeeded` | `completed` | Standing authorization requires bounded divergent research and governed component requisition after narrow-path saturation signals. | `40_output/divergence-policy.md` |
| `mercury-task-0018` | `mercury-divergent-path-research` | `experiment` | Research materially divergent local forecasting paths | `succeeded` | `completed` | Direct multi-horizon GBDT ranked highest expected-value divergent path; hierarchical, latent-factor, and TFT branches deferred. | `40_output/component-requisition-direct-gbdt.yaml` |
| `mercury-task-0019` | `mercury-direct-gbdt-requisition` | `harness_maintenance` | Requisition trusted direct-horizon GBDT component | `planned` | `not_started` | Component acceptance requires typed contract, synthetic leakage tests, and local-only isolation. | `40_output/component-requisition-direct-gbdt.yaml` |
| `mercury-task-0020` | `mercury-direct-gbdt-validation` | `experiment` | Run direct multi-horizon GBDT on frozen local holdout | `succeeded` | `completed` | RMSLE 0.4609337296, a 0.1561066865 absolute improvement over recursive seasonal baseline. | `30_evidence/mercury-direct-gbdt-validation-001-tool-run.json` |
| `mercury-task-0021` | `mercury-direct-gbdt-submission` | `operations` | Submit validated direct GBDT candidate | `succeeded` | `completed` | Kaggle accepted submission 55489163; score pending at record time. | `30_evidence/mercury-direct-gbdt-submission-001-submission-record.json` |

## Usage events

| usage_event_id | task_event_id | domain | action_type | metering_status | receipt_ref | notes |
|---|---|---|---|---|---|---|
| `mercury-usage-0001` | `mercury-task-0001` | `challenge_intake` | `intake_handoff` | `not_applicable` | `not_applicable` | No token-metered runtime or challenge execution. |
| `mercury-usage-0002` | `mercury-task-0002` | `operations` | `kaggle_cli_download` | `not_available` | `not_available` | Kaggle CLI did not supply a token or billed-cost receipt. Network transfer volume is represented by the downloaded archive, not a token estimate. |
| `mercury-usage-0003` | `mercury-task-0003` | `challenge_intake` | `safe_local_intake` | `not_applicable` | `not_applicable` | Deterministic local intake; no token-metered runtime. |
| `mercury-usage-0004` | `mercury-task-0005` | `decision_governance` | `initial_import_decision_review` | `not_available` | `not_available` | Specialist runtime provided no authoritative token receipt. |
| `mercury-usage-0005` | `mercury-task-0006` | `dataset` | `create_dataset_version` | `not_applicable` | `not_applicable` | Deterministic local metadata operation; no token-metered runtime. |
| `mercury-usage-0006` | `mercury-task-0007` | `dataset` | `time_series_characterization` | `not_applicable` | `not_applicable` | Deterministic local analysis; no token-metered runtime. |
| `mercury-usage-0007` | `mercury-task-0008` | `experiment` | `experiment_plan_compilation` | `not_applicable` | `not_applicable` | Non-executable local planning; no token-metered runtime. |
| `mercury-usage-0008` | `mercury-task-0010` | `harness_maintenance` | `toolbox_build_and_test` | `not_applicable` | `not_applicable` | Local code and synthetic-fixture verification; no token-metered runtime. |
| `mercury-usage-0009` | `mercury-task-0011` | `experiment` | `seasonal_naive_baseline_run` | `not_applicable` | `not_applicable` | Deterministic local tool run; no token-metered runtime. |
| `mercury-usage-0010` | `mercury-task-0012` | `experiment` | `seasonal_naive_test_forecast` | `not_applicable` | `not_applicable` | Deterministic local tool run; no token-metered runtime. |
| `mercury-usage-0011` | `mercury-task-0013` | `operations` | `kaggle_cli_submission` | `not_available` | `not_available` | Kaggle CLI returned no token or billed-cost receipt. |
| `mercury-usage-0012` | `mercury-task-0014` | `decision_governance` | `continuation_review` | `not_applicable` | `not_applicable` | Evidence interpretation without a token-metered runtime. |
| `mercury-usage-0013` | `mercury-task-0015` | `experiment` | `recursive_seasonal_baseline_run` | `not_applicable` | `not_applicable` | Deterministic local tool run; no token-metered runtime. |
| `mercury-usage-0014` | `mercury-task-0016` | `operations` | `kaggle_cli_submission` | `not_available` | `not_available` | Kaggle CLI returned no token or billed-cost receipt. |
| `mercury-usage-0015` | `mercury-task-0017` | `decision_governance` | `divergence_policy_recording` | `not_applicable` | `not_applicable` | Local durable policy record; no token-metered runtime. |
| `mercury-usage-0016` | `mercury-task-0018` | `experiment` | `divergent_path_research` | `not_available` | `not_available` | Research runtime did not provide an authoritative token receipt. |

## Current outcome snapshot

| project_outcome_status | validation_status | production_status | rationale |
|---|---|---|---|
| `pending` | `partial` | `not_deployed` | Local baseline and one public Kaggle score recorded; continuation requires a separately approved diagnostic plan. |
