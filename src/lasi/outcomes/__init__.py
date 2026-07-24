"""Outcome state and append-only event services."""

from .errors import (
    InvalidOutcomeTransition,
    MissingDeploymentApproval,
    MissingProductionEvidence,
    OutcomeNotFound,
    UnknownOutcomeStatus,
)
from .service import (
    OUTCOME_STATUSES,
    OutcomeService,
    OutcomeStore,
    allowed_transitions,
)

__all__ = [
    "OUTCOME_STATUSES",
    "InvalidOutcomeTransition",
    "MissingDeploymentApproval",
    "MissingProductionEvidence",
    "OutcomeNotFound",
    "OutcomeService",
    "OutcomeStore",
    "UnknownOutcomeStatus",
    "allowed_transitions",
]
