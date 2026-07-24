Authority Boundaries
====================

Subsystems and responsibilities

- Scientist Provider: recommends via `ScientistReview` artifacts; MUST NOT execute tools or change data.
- Decision System: authorizes, blocks, or escalates proposals via `Decision Record` artifacts.
- Tool Registry: constrains available tools and records tool metadata.
- Dataset System: owns dataset versions and manifests; controls ingestion and canonical storage.
- Knowledge Curator: drafts knowledge documents and proposals but DOES NOT approve facts/policies.
- Remote Runner: executes remote jobs but local harness remains the authority for recording artifacts.

High-consequence actions (require human approval)

- label changes, dataset merges/splits
- dataset deletions or raw data exports
- model deployments or training on private data
- promoting hypotheses to facts or policies
