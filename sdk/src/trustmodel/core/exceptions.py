"""SDK Exception definitions."""

from typing import Any, Optional


class TrustModelError(Exception):
    """Base exception for all TrustModel SDK errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "TRUSTMODEL_ERROR"
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} - {self.details}"
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(TrustModelError):
    """Raised when SDK configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        missing_fields: Optional[list[str]] = None,
    ) -> None:
        details = {}
        if missing_fields:
            details["missing_fields"] = missing_fields
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)


class AuthenticationError(TrustModelError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        reason: Optional[str] = None,
    ) -> None:
        details = {}
        if reason:
            details["reason"] = reason
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details)


class APIError(TrustModelError):
    """Raised when an API request fails."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[dict[str, Any]] = None,
    ) -> None:
        details: dict[str, Any] = {}
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response"] = response_body
        super().__init__(message, code="API_ERROR", details=details)
        self.status_code = status_code


class CertificateError(TrustModelError):
    """Raised when certificate operations fail."""

    def __init__(
        self,
        message: str,
        certificate_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        details: dict[str, Any] = {}
        if certificate_id:
            details["certificate_id"] = certificate_id
        if reason:
            details["reason"] = reason
        super().__init__(message, code="CERTIFICATE_ERROR", details=details)


class CertificateExpiredError(CertificateError):
    """Raised when a certificate has expired."""

    def __init__(
        self,
        certificate_id: str,
        expired_at: str,
    ) -> None:
        super().__init__(
            message=f"Certificate {certificate_id} expired at {expired_at}",
            certificate_id=certificate_id,
            reason="expired",
        )
        self.details["expired_at"] = expired_at


class CertificateRevokedError(CertificateError):
    """Raised when a certificate has been revoked."""

    def __init__(
        self,
        certificate_id: str,
        revoked_at: str,
        revocation_reason: Optional[str] = None,
    ) -> None:
        super().__init__(
            message=f"Certificate {certificate_id} was revoked",
            certificate_id=certificate_id,
            reason="revoked",
        )
        self.details["revoked_at"] = revoked_at
        if revocation_reason:
            self.details["revocation_reason"] = revocation_reason


class EvaluationError(TrustModelError):
    """Raised when evaluation operations fail."""

    def __init__(
        self,
        message: str,
        evaluation_id: Optional[str] = None,
        suite: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        details: dict[str, Any] = {}
        if evaluation_id:
            details["evaluation_id"] = evaluation_id
        if suite:
            details["suite"] = suite
        if reason:
            details["reason"] = reason
        super().__init__(message, code="EVALUATION_ERROR", details=details)


class ProtocolError(TrustModelError):
    """Raised when TACP protocol operations fail."""

    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        message_type: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        details: dict[str, Any] = {}
        if session_id:
            details["session_id"] = session_id
        if message_type:
            details["message_type"] = message_type
        if reason:
            details["reason"] = reason
        super().__init__(message, code="PROTOCOL_ERROR", details=details)


class SessionError(ProtocolError):
    """Raised when session operations fail."""

    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        super().__init__(message, session_id=session_id, reason=status)
        if status:
            self.details["status"] = status


class TrustVerificationError(ProtocolError):
    """Raised when trust verification between agents fails."""

    def __init__(
        self,
        message: str,
        agent_id: Optional[str] = None,
        required_capabilities: Optional[list[str]] = None,
        missing_capabilities: Optional[list[str]] = None,
    ) -> None:
        details: dict[str, Any] = {"reason": "trust_verification_failed"}
        if agent_id:
            details["agent_id"] = agent_id
        if required_capabilities:
            details["required_capabilities"] = required_capabilities
        if missing_capabilities:
            details["missing_capabilities"] = missing_capabilities
        super().__init__(message, reason="trust_verification_failed")
        self.details.update(details)


class TracingError(TrustModelError):
    """Raised when tracing operations fail."""

    def __init__(
        self,
        message: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        details: dict[str, Any] = {}
        if trace_id:
            details["trace_id"] = trace_id
        if span_id:
            details["span_id"] = span_id
        if reason:
            details["reason"] = reason
        super().__init__(message, code="TRACING_ERROR", details=details)


class RetryableError(TrustModelError):
    """Base class for errors that can be retried."""

    def __init__(
        self,
        message: str,
        code: str,
        retry_after: Optional[float] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code=code, details=details or {})
        self.retry_after = retry_after
        if retry_after:
            self.details["retry_after"] = retry_after


class RateLimitError(RetryableError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(
            message,
            code="RATE_LIMIT_ERROR",
            retry_after=retry_after,
        )


class ServerError(RetryableError):
    """Raised when server returns a 5xx error."""

    def __init__(
        self,
        message: str,
        status_code: int,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(
            message,
            code="SERVER_ERROR",
            retry_after=retry_after,
            details={"status_code": status_code},
        )
        self.status_code = status_code
