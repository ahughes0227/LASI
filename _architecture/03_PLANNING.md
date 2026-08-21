# Planning

The planner receives a bounded MemoryContext, Goal, registered OperatorSpec contracts,
and ExplorationDirective values. It returns a strict Plan.

The provider-neutral gateway is implemented with the LiteLLM Python SDK. A persisted
PlannerProfile fixes the service identity, model, endpoint, temperature, timeouts, and
bounded retry/repair counts. Profile IDs are immutable; changed settings require a new
profile identity. The model cannot define callables, shell commands, graph
nodes, permissions, or operator registrations.

Plans are immutable and content-addressed. Mutation after verification invalidates the
decision.

Each invocation records model/profile/template identity, request and response digests,
latency, token usage, cost when available, and a structured error category. Raw request
and response bodies are kept separately in private 0600 files. Transient provider errors
and invalid structured output have independent bounded retry budgets.
