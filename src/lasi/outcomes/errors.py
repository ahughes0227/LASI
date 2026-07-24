"""Errors raised by outcome state transitions."""


class OutcomeError(ValueError):
    """Base error for invalid outcome operations."""


class OutcomeNotFound(OutcomeError):
    """Raised when an operation requires an existing project or outcome."""


class UnknownOutcomeStatus(OutcomeError):
    """Raised when a status is outside the controlled outcome vocabulary."""


class InvalidOutcomeTransition(OutcomeError):
    """Raised when a requested status change is not allowed."""


class MissingProductionEvidence(OutcomeError):
    """Raised when production success is recorded without evidence."""


class MissingDeploymentApproval(OutcomeError):
    """Raised when deployment-related outcome evidence lacks authorization."""
