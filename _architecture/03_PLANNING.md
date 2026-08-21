# Planning

The planner receives a bounded MemoryContext, Goal, registered OperatorSpec contracts,
and ExplorationDirective values. It returns a strict Plan.

LangChain may compose prompts, models, retrievers, and structured-output parsers inside
the planner adapter. The model cannot define callables, shell commands, graph nodes,
permissions, or operator registrations. Dynamic chains are planning implementation
details, not runtime authority.

Plans are immutable and content-addressed. Mutation after verification invalidates the
decision.
