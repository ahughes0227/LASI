Skill: Decision Review
======================

Purpose
-------

Record human decisions that authorize, block, or scope actions. Decisions must include rationale and scope.

When to use
-----------

After scientist reviews or when a workflow step requires human authorization.

Required inputs
---------------

- `scientist_review.md` or explicit proposal artifacts.

Required outputs
----------------

- `decision_record.md` with decision, rationale, author, and scope.

Files to read first
-------------------

- _core/authority_boundaries.md

Forbidden actions
-----------------

- Decision agents MUST NOT unilaterally run high-consequence actions; they only record decisions.

Completion criteria
-------------------

- A decision record exists that clearly states allowed actions and any vetoes.
