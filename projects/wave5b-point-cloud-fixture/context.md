# Wave 5B Point-Cloud Fixture

This is a public, synthetic binary point-cloud project used by the Wave 5B
end-to-end integration tests. It represents binary scratch classification with
two labels and no real industrial data.

The tests generate the NPZ point clouds and Parquet manifest in a temporary
workspace so the repository remains source-only and the fixture is reproducible.

Scenarios covered by `tests/integration/test_wave5b_fixture.py`:

- successful validation, characterization, planning, authorization, tool execution, provider review, and report rendering
- dataset validation failure
- approval, privacy, and non-comparable-comparison blocks
- tool failure and partial success
- invalid provider response and stop recommendation
- append-only outcome transition history
