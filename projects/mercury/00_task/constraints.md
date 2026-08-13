# Constraints

- Privacy mode: `local_only`
- Challenge mode: protected local benchmark
- Internet policy: `deny` after intake, except the separately recorded Kaggle CLI download and per-submission decisions.
- External data policy: `deny`
- Hidden-label policy: `evaluator_only`
- Execution backend: `local_only`
- External scientist providers: `blocked_by_benchmark_isolation`
- Remote execution: `blocked_by_benchmark_isolation`
- Arbitrary subprocesses: `blocked_by_benchmark_isolation`
- Dataset and benchmark mutations: `not_authorized`
- Submission: requires a separately scoped decision and user-authorized Kaggle account/team.
- Budget policy: no fixed cap; record per-task resource usage and task outcome. Approved plans must still declare resource estimates and stop conditions.

Public metadata observed before benchmark isolation is not a substitute for local rules, schemas, or source files.
