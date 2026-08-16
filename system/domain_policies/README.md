# Domain policies

Domain policies are data-only YAML files describing deterministic project or
system rules. The registry validates them as `DomainPolicy` contracts and never
imports or executes content from policy files.

Only approved policies are evaluated. A policy can allow planning, block
planning, or require a named approval action; it cannot authorize execution or
bypass `DecisionGate`. Approved policies must include provenance references,
and policy changes should be reviewed as governed policy changes.

Policy files may be placed in this directory or nested directories and must use
the `.yaml` extension. This packet intentionally provides no production policy
files.
