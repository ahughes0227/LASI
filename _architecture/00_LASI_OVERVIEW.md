# LASI overview

LASI is a governed research loop for machine-learning work:

    memory -> exploration pressure -> LLM plan -> deterministic verification
           -> rigid execution -> recorded evidence -> memory

The planner is creative but powerless. It returns a typed Plan made only from
registered operators. The verifier is deterministic and checks identity grants,
operator risk, evidence references, dependencies, and approvals. The executor runs
only the exact verified plan digest.

LASI distinguishes the SQLite authority ledger, artifact storage, Graphiti temporal
retrieval, confidence-bearing beliefs, planner recommendations, deterministic
authorization, and LangGraph orchestration.

Graphiti and LangGraph are replaceable infrastructure. Neither is an authority.
