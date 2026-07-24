"""Errors raised at the scientist-provider boundary."""

from typing import Any


class ProviderException(Exception):
    """Base exception for provider failures."""

    def __init__(self, message: str, *, error_type: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


class ProviderPrivacyError(ProviderException):
    def __init__(self, message: str) -> None:
        super().__init__(message, error_type="privacy_policy_block")


class ProviderValidationError(ProviderException):
    def __init__(self, message: str, *, error_type: str = "schema_validation_failure") -> None:
        super().__init__(message, error_type=error_type)


class ProviderCallError(ProviderException):
    def __init__(self, message: str, *, error_type: str = "provider_unavailable") -> None:
        super().__init__(
            message, error_type=error_type, retryable=error_type in {"timeout", "rate_limit"}
        )


def error_details(error: ProviderException) -> dict[str, Any]:
    """Return structured details without making the error an authorization decision."""
    return {"error_type": error.error_type, "message": str(error), "retryable": error.retryable}
