# Toolbox Acceptance — Direct-Horizon GBDT v0.1.0

## Status

`accepted_for_registered_local_use`

The direct-horizon GBDT branch is accepted under the standing Mercury authorization after synthetic validation. It is materially divergent from recursive seasonal-naive forecasting: it uses global nonlinear direct-horizon learning with calendar, promotion, and past-sales features.

## Safety conditions

- Calendar-date target joins, with targets strictly before each origin cutoff during fitting.
- Non-null unique train/test IDs and panel keys; output ID alignment verified.
- Frozen family vocabulary between fit and inference.
- Protected local read/write allowlists and deny-all profile.
- No external data, supplemental sources, remote execution, providers, subprocesses, or network activity.

## Evidence

- Implementation: `services/timeseries/direct_gbdt.py`
- Synthetic tests: `tests/test_direct_gbdt.py`
- Requisition: `40_output/component-requisition-direct-gbdt.yaml`
- Approval: `40_output/approvals/APP-MERCURY-DIRECT-GBDT-COMPONENT-0001.yaml`

This acceptance is toolbox-only. The next experiment requires an exact local plan and decision.
