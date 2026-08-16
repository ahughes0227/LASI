# Workflow Builder

Builds governed JSON workflow packages for LASI. Accepts a typed workflow
definition or structured workflow intent and produces a deduplication
resolution, frozen build plan, fixed package shell, validation evidence, and a
registration proposal.

The builder must preserve LASI boundaries: workflow JSON declares routing,
artifact handoffs, gates, and bounded extensions; SQLite remains operational
truth; decisions authorize execution; prompts, rubrics, and profiles remain
versioned assets; and registration is separate from proposal.

It must resolve REUSE, COMPOSE, EXTEND, or NEW before research, keep research
bounded to recorded gaps, and fail closed on unknown bindings, invalid graphs,
missing skip handling, and unsafe execution bypasses.
