Step: 05 Run Experiments
========================

Purpose
-------

Execute experiments from the experiment plan and collect diagnostic packets.

Inputs
------

- `experiment_plan.md`

Actions
-------

1. For each experiment, run `remote_execution` (or local runner) as specified.
2. Collect logs, metrics, and artifacts into diagnostic packets.

Skill
-----

remote_execution

Expected output
---------------

- `remote_run_record.md` files and a combined `diagnostic_packet` folder.

Stop / Escalation
-----------------

- If runs consistently fail, pause and hand to scientist_review with failure evidence.

Handoff
-------

Pass diagnostic packets to `06_scientist_review`.
