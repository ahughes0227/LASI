# Experiment Plan — MERCURY-PLAN-0001

## Plan status

`draft_requires_decision`

This is a controlled, non-executable plan. It does not authorize tools, feature generation, training, prediction, or Kaggle submission.

## Identity and scope

- Plan ID: `MERCURY-PLAN-0001`
- Project ID: `mercury`
- Dataset version: `mercury-store-sales:v1`
- Experiment type: `baseline_probe`
- Backend: `local`
- Privacy mode: `local_only`
- Benchmark isolation: network, remote execution, external providers, external data, arbitrary subprocesses, and hidden-label access denied.

## Hypothesis

A chronological, nonnegative seasonal naive baseline with no supplemental features will establish a valid local reference and expose whether the approved temporal split and past-only feature policy are operationally sound. Official metric confirmation remains a plan dependency.

## Reason and ordered tool runs

| Order | Planned tool run | Inputs | Controlled behavior | Expected artifact |
|---|---|---|---|---|
| 1 | `validate_time_series_split` | immutable train CSV, declared cutoff, panel keys | Verify chronological holdout, no target in validation features, no duplicate panel keys | split definition and audit result |
| 2 | `seasonal_naive_baseline` | same dataset version and split | Use only prior observed sales at matching panel/calendar position; no supplemental tables, no future data, fixed seed | validation predictions, RMSLE, segment metrics, run log |
| 3 | `error_analysis` | baseline validation predictions | Bucket RMSLE/error by forecast horizon, store, family, and zero/nonzero target regime | error-bucket summary |

The current registry/tool availability for these time-series-specific tools is `not_available`; this plan is therefore not executable until a decision evaluates either registered-tool availability or an approved toolbox proposal. No arbitrary script is authorized as a substitute.

## Evaluation policy proposal

- Primary metric: `not_locally_verified`; public metadata reports RMSLE/minimize, which must be confirmed through an official rules artifact or an explicit user confirmation before execution.
- Candidate holdout: last 16 observed dates ending 2017-08-15, mirroring the observed test horizon length.
- Comparability: directly comparable only if all runs use `mercury-store-sales:v1`, the same cutoff, same metric implementation, and past-only feature construction.
- Prediction safety: clip predictions at zero before RMSLE; record any clipping count.

The holdout is a proposal, not a confirmed official evaluation policy. It must be recorded in the decision and run configuration before execution.

## Success and failure criteria

- **Success:** split audit passes; required artifacts are complete; the confirmed primary metric is recorded with reproducible configuration and nonnegative predictions.
- **Failure:** temporal leakage or duplicate panel key; missing required artifact; use of future observations; unregistered tool; or a mismatch between plan and decision.
- **Stop:** stop this branch if split integrity cannot be established. Do not replace it with random validation.

## Resource and task tracking

No fixed budget cap applies. Each run must record wall time, memory/runtime information when available, domain `experiment`, explicit task success/failure, and token usage as `not_applicable` or `not_available` unless an authoritative receipt exists.

## Handoff after decision

If allowed, local registered tools produce structured `ToolRunResult` records and artifacts, then hand off a diagnostic packet to error analysis. No scientist-provider call is planned. A Kaggle submission is a separate high-risk decision after a validated prediction artifact exists.

## Provenance and artifact contract

- **READ:** `10_context/dataset_characterization.md`; dataset manifest/version; time-aware audit; ChallengeSpec.
- **DO:** compile and evaluate the plan only; run nothing before a decision.
- **WRITE:** a decision record, then isolated experiment context and structured tool-run evidence if allowed.
- Sources: `30_evidence/mercury-store-sales-v1-profile.json`; `30_evidence/mercury-store-sales-v1-time-aware-audit.json`; `30_evidence/mercury-challenge-spec.json`.
