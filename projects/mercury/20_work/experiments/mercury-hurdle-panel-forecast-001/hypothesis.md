# Hypothesis

`MERCURY-HURDLE-PANEL-FORECAST-001` is a research-only draft. It does not authorize component construction, tool execution, prediction generation, submission, or any modification of challenge data.

The direct multi-horizon GBDT's remaining RMSLE error may be materially driven by the panel's zero-inflated sales distribution (939,130 of 3,000,888 observed training targets are zero). A past-only, direct-horizon hurdle forecaster—separating `sales == 0` from conditional `log1p(sales)` magnitude and recombining the expected sales—can test that distributional assumption without changing the frozen validation boundary.

**Expected signal:** lower frozen-holdout RMSLE than `0.4609337296401332`, with an attributable improvement in zero/nonzero error buckets rather than only a global aggregate change.

**Contradictory signal:** no meaningful RMSLE improvement, or worse performance in either zero or positive-target buckets. That would weaken the target-distribution diagnosis rather than justify parameter tuning of the direct GBDT path.
