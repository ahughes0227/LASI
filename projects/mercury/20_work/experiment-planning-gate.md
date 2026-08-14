# Mercury Experiment-Planning Gate

**Project:** mercury  
**Proposed objective:** Improve the legitimate Store Sales challenge score; no outcome, including winning, is promised.  
**Plan state:** `superseded_by_experiment-plan-0001` — this historical non-executable gate is not an ExperimentPlan authorization.

## Evidence and provenance

- Current inputs, dataset version, and characterization are recorded in `10_context/local-intake.md`, `10_context/dataset_characterization.md`, and `30_evidence/mercury-store-sales-v1-dataset-version.json`.
- This gate is retained as historical pre-intake planning evidence. The active plan is `20_work/experiment-plan-0001.md`.

## Dependencies before any plan or tool run

1. A locally supplied dataset must complete governed intake, and a separate approval decision must authorize creation of its immutable initial-import dataset version.
2. That dataset version must have a completed characterization, including schema, target, date coverage, entity/store-product keys, missingness, duplicates, and evaluation/submission constraints.
3. A decision record must explicitly authorize the scoped plan and permitted local tools.
4. Benchmark isolation must remain in force: no network access, external providers, remote execution, arbitrary subprocesses, or hidden-label access.

**Authorized state:** No model, diagnostic, validation, or submission tool execution is authorized. No remote or external work is authorized.

## Suggested controlled experiment sequence — only after all dependencies

| Order | Proposed experiment | Inputs and controlled change | Metrics / expected evidence | Estimated cost | Success criteria | Stop conditions |
|---|---|---|---|---|---|---|
| 1 | Temporal baseline probe | Characterized immutable dataset version; documented time-based split; simple seasonality/lag baseline; fixed seed and local approved tool | Challenge-aligned validation metric; per-horizon/per-store-family error; prediction coverage | Unknown until intake; local-only, bounded | Produces reproducible baseline metrics and required artifacts | Stop if split/evaluation policy is undefined, leakage is detected, or artifacts are incomplete |
| 2 | Feature ablation | Same version, split, metric, and seed; add only documented calendar, lag, and rolling features relative to baseline | Validation delta and segment errors; directly comparable result | Unknown until characterization; local-only, bounded | Meets pre-approved minimum meaningful improvement without degraded required segments | Stop if temporal leakage, non-comparability, or budget limit occurs |
| 3 | Capacity comparison | Best prior controlled configuration; vary one approved model-capacity choice only | Same validation metric, runtime, and segment errors | Unknown until approved plan; local-only, bounded | Improvement exceeds pre-approved threshold and is stable across approved temporal folds | Stop if gains are not stable, compute budget is reached, or required artifacts are missing |
| 4 | Error analysis | Best comparable validation predictions and characterized metadata | Error by horizon, store, family, promotion/holiday regime, and missing-data regime | Low; local-only, bounded | Identifies a documented, actionable failure concentration or supports stopping further model work | Stop if predictions cannot be joined to approved metadata or validation integrity is uncertain |

## Temporal validation concern

Store-sales observations are time-dependent. Random row splits are presumptively invalid because future information can leak into training. The characterization and approved evaluation policy must define chronological train/validation boundaries, forecast horizon, feature availability cutoff, gap/embargo where appropriate, and whether rolling-origin folds are required. All comparisons must use identical temporal splits and dataset version; otherwise the comparison status is `not_comparable`.

## Required artifact contract after authorization

### Planning-gate contract

- **READ:** `00_task/objective.md`, `00_task/constraints.md`, `10_context/challenge_intake_handoff.md`, locally verified characterization and evaluation-policy records when available, and the applicable decision record.
- **DO:** identify missing dependencies and compile a proposed controlled sequence; do not execute tools or authorize actions.
- **WRITE:** this planning gate and, after dependencies are satisfied, a durable `ExperimentPlan` and isolated experiment-context records.

For each isolated `20_work/experiments/<experiment_id>/` context: `hypothesis.md`, `inputs.md`, `config.yaml`, `results.md`, `artifacts.md`, and `critique.md`. Required provenance includes project ID, dataset version, plan/decision IDs, tool and code versions, seed, local backend, evaluation-policy reference, configuration hash, and artifact references. Expected evidence includes metrics, validation predictions, split definition, environment record, and run log.

**No model execution has occurred or is requested by this gate.**
