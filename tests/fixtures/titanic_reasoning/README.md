# Titanic reasoning benchmark v1

This fixture freezes the existing Kaggle Titanic project as LASI's first
change-over-change reasoning benchmark. It evaluates three distinct dimensions:

1. **Reasoning accuracy** is the fraction of six evidence-linked checks passed.
   It is the primary KPI because the benchmark is intended to improve LASI's
   research judgment, not merely its classifier.
2. **Wall-clock seconds** measure end-to-end speed. Missing historical timing is
   `not_available`, never zero.
3. **Authoritative total tokens** measure reasoning efficiency. Missing runtime
   receipts are `not_available`, never estimated from text and never treated as
   zero.

Local holdout and Kaggle public accuracy are outcome guardrails. A future change
should not claim better reasoning by degrading the predictive result or by
overfitting the local holdout. Runs are comparable only when benchmark version,
dataset version, evidence packet hash, and ordered reasoning checks match.

The legacy baseline uses the title/family experiment because it was the best run
produced by this project: 0.8379888268 local accuracy and 0.77511 public accuracy.
The prior LASI public best of 0.78229 remains the external target to beat. The
legacy report did not record end-to-end duration, lacked authoritative receipts
for three agent actions, and did not provide a performance-gap diagnosis; those
limitations are preserved explicitly.
