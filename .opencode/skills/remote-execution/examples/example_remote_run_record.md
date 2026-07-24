Example only. Not real project data.

# Remote Run Record — RUN-REMOTE-0001

- run_id: RUN-REMOTE-0001
- project_id: PROJECT-EX1
- host_profile: gpu-cluster-1
- command: evaluation job
- started_at: 2026-05-30T12:00:00Z
- finished_at: 2026-05-30T12:30:00Z
- status: success
- artifacts:
  - s3://example-bucket/projects/PROJECT-EX1/artifacts/nighttime_eval/results.csv

Note: Remote runs must be authorized by a decision record including `remote_host_profile`.
