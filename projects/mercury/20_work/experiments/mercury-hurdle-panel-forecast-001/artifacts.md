# Expected artifacts and WRITE contract

All proposed outputs are confined to this experiment subcontext (or registered immutable artifact storage after an authorized run):

1. `split.json` — frozen date boundary, keys, row counts, and past-only audit.
2. `resolved-experiment-spec.json` — version-pinned, configuration-resolved component graph and hash.
3. `validation_predictions.csv` — row key, date, actual sales, positive probability, conditional magnitude, recombined nonnegative prediction, horizon.
4. `metrics.json` — RMSLE, zero/nonzero bucket RMSLE, clipping count, counts, and comparison metadata.
5. `feature-lineage.json` — each feature's source, availability timestamp, and no-future-target attestation.
6. `environment.json`, `run-log.txt`, and structured `ToolRunResult` — tool/component versions, seed, backend, runtime, status, and errors.
7. `critique.md` update — interpretation, including a negative result.

No submission CSV is an expected artifact. No write may target the read-only official input root, dataset version, benchmark specification, or another experiment context.
