"""
Custom Exception Hierarchy for Broker Copilot

Provides a comprehensive set of domain-specific exceptions
with error codes, HTTP status mapping, and context support.
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""
    
    # General errors (1xxx)
    UNKNOWN_ERROR = "ERR_1000"
    INTERNAL_ERROR = "ERR_1001"
    CONFIGURATION_ERROR = "ERR_1002"
    VALIDATION_ERROR = "ERR_1003"
    NOT_FOUND = "ERR_1004"
    CONFLICT = "ERR_1005"
    
    # Authentication/Authorization (2xxx)
    AUTHENTICATION_REQUIRED = "ERR_2000"
    AUTHENTICATION_FAILED = "ERR_2001"
    TOKEN_EXPIRED = "ERR_2002"
    TOKEN_INVALID = "ERR_2003"
    TOKEN_REFRESH_FAILED = "ERR_2004"
    AUTHORIZATION_DENIED = "ERR_2005"
    INSUFFICIENT_PERMISSIONS = "ERR_2006"
    OAUTH_STATE_INVALID = "ERR_2007"
    OAUTH_CALLBACK_ERROR = "ERR_2008"
    
    # External Services (3xxx)
    EXTERNAL_SERVICE_ERROR = "ERR_3000"
    EXTERNAL_SERVICE_UNAVAILABLE = "ERR_3001"
    EXTERNAL_SERVICE_TIMEOUT = "ERR_3002"
    RATE_LIMIT_EXCEEDED = "ERR_3003"
    
    # Connector errors (4xxx)
    CONNECTOR_ERROR = "ERR_4000"
    CONNECTOR_AUTH_REQUIRED = "ERR_4001"
    CONNECTOR_NOT_CONFIGURED = "ERR_4002"
    MICROSOFT_GRAPH_ERROR = "ERR_4010"
    SALESFORCE_ERROR = "ERR_4020"
    HUBSPOT_ERROR = "ERR_4030"
    
    # LLM errors (5xxx)
    LLM_ERROR = "ERR_5000"
    LLM_API_ERROR = "ERR_5001"
    LLM_RATE_LIMIT = "ERR_5002"
    LLM_CONTENT_FILTER = "ERR_5003"
    LLM_FUNCTION_ERROR = "ERR_5004"
    
    # Email errors (6xxx)
    EMAIL_ERROR = "ERR_6000"
    EMAIL_SEND_FAILED = "ERR_6001"
    EMAIL_TEMPLATE_ERROR = "ERR_6002"
    EMAIL_PROVIDER_ERROR = "ERR_6003"
    EMAIL_NOT_FOUND = "ERR_6004"
    EMAIL_ALREADY_SENT = "ERR_6005"
    
    # PDF errors (7xxx)
    PDF_ERROR = "ERR_7000"
    PDF_GENERATION_FAILED = "ERR_7001"
    PDF_TEMPLATE_ERROR = "ERR_7002"


class BrokerCopilotError(Exception):
    """
    Base exception for all Broker Copilot errors.
    
    Provides:
    - Error code for categorization
    - HTTP status code mapping
    - Context dictionary for additional details
    - User-friendly message separation from technical details
    """
    
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
    http_status: int = 500
    
    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[ErrorCode] = None,
        http_status: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        user_message: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.error_code
        self.http_status = http_status or self.__class__.http_status
        self.context = context or {}
        self.cause = cause
        self.user_message = user_message or message
        
        # Chain exceptions
        if cause:
            self.__cause__ = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "error": True,
            "error_code": self.error_code.value,
            "message": self.user_message,
            "detail": self.message,
        }
        if self.context:
            result["context"] = self.context
        return result
    
    def __str__(self) -> str:
        parts = [f"[{self.error_code.value}] {self.message}"]
        if self.context:
            parts.append(f"Context: {self.context}")
        if self.cause:
            parts.append(f"Caused by: {type(self.cause).__name__}: {self.cause}")
        return " | ".join(parts)


class ConfigurationError(BrokerCopilotError):
    """Raised when configuration is missing or invalid."""
    error_code = ErrorCode.CONFIGURATION_ERROR
    http_status = 500


class ValidationError(BrokerCopilotError):
    """Raised when input validation fails."""
    error_code = ErrorCode.VALIDATION_ERROR
    http_status = 400


class NotFoundError(BrokerCopilotError):
    """Raised when a requested resource is not found."""
    error_code = ErrorCode.NOT_FOUND
    http_status = 404


class ConflictError(BrokerCopilotError):
    """Raised when there's a conflict with existing data."""
    error_code = ErrorCode.CONFLICT
    http_status = 409


# =============================================================================
# Authentication/Authorization Errors
# =============================================================================

class AuthenticationError(BrokerCopilotError):
    """Base class for authentication errors."""
    error_code = ErrorCode.AUTHENTICATION_FAILED
    http_status = 401


class TokenExpiredError(AuthenticationError):
    """Raised when an access token has expired."""
    error_code = ErrorCode.TOKEN_EXPIRED


class TokenInvalidError(AuthenticationError):
    """Raised when a token is malformed or invalid."""
    error_code = ErrorCode.TOKEN_INVALID


class TokenRefreshError(AuthenticationError):
    """Raised when token refresh fails."""
    error_code = ErrorCode.TOKEN_REFRESH_FAILED


class OAuthStateError(AuthenticationError):
    """Raised when OAuth state is invalid (possible CSRF)."""
    error_code = ErrorCode.OAUTH_STATE_INVALID


class OAuthCallbackError(AuthenticationError):
    """Raised when OAuth callback fails."""
    error_code = ErrorCode.OAUTH_CALLBACK_ERROR


class AuthorizationError(BrokerCopilotError):
    """Raised when access is denied due to permissions."""
    error_code = ErrorCode.AUTHORIZATION_DENIED
    http_status = 403


# =============================================================================
# External Service Errors
# =============================================================================

class ExternalServiceError(BrokerCopilotError):
    """Base class for external service errors."""
    error_code = ErrorCode.EXTERNAL_SERVICE_ERROR
    http_status = 502
    
    def __init__(
        self,
        message: str,
        *,
        service_name: str = "unknown",
        status_code: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        context.update({
            "service": service_name,
            "service_status_code": status_code,
        })
        super().__init__(message, context=context, **kwargs)
        self.service_name = service_name
        self.service_status_code = status_code


class ServiceUnavailableError(ExternalServiceError):
    """Raised when an external service is unavailable."""
    error_code = ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE
    http_status = 503


class ServiceTimeoutError(ExternalServiceError):
    """Raised when an external service times out."""
    error_code = ErrorCode.EXTERNAL_SERVICE_TIMEOUT
    http_status = 504


class RateLimitError(ExternalServiceError):
    """Raised when rate limit is exceeded."""
    error_code = ErrorCode.RATE_LIMIT_EXCEEDED
    http_status = 429
    
    def __init__(
        self,
        message: str,
        *,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.context["retry_after_seconds"] = retry_after


# =============================================================================
# Connector Errors
# =============================================================================

class ConnectorError(BrokerCopilotError):
    """Base class for data connector errors."""
    error_code = ErrorCode.CONNECTOR_ERROR
    http_status = 502


class ConnectorAuthRequiredError(ConnectorError):
    """Raised when connector authentication is required."""
    error_code = ErrorCode.CONNECTOR_AUTH_REQUIRED
    http_status = 401


class ConnectorNotConfiguredError(ConnectorError):
    """Raised when a connector is not properly configured."""
    error_code = ErrorCode.CONNECTOR_NOT_CONFIGURED
    http_status = 500


class MicrosoftGraphError(ConnectorError):
    """Raised for Microsoft Graph API specific errors."""
    error_code = ErrorCode.MICROSOFT_GRAPH_ERROR


class SalesforceError(ConnectorError):
    """Raised for Salesforce API specific errors."""
    error_code = ErrorCode.SALESFORCE_ERROR


class HubSpotError(ConnectorError):
    """Raised for HubSpot API specific errors."""
    error_code = ErrorCode.HUBSPOT_ERROR


# =============================================================================
# LLM Errors
# =============================================================================

class LLMError(BrokerCopilotError):
    """Base class for LLM-related errors."""
    error_code = ErrorCode.LLM_ERROR
    http_status = 502


class LLMAPIError(LLMError):
    """Raised when LLM API returns an error."""
    error_code = ErrorCode.LLM_API_ERROR


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is exceeded."""
    error_code = ErrorCode.LLM_RATE_LIMIT
    http_status = 429


class LLMContentFilterError(LLMError):
    """Raised when LLM content filter blocks the request."""
    error_code = ErrorCode.LLM_CONTENT_FILTER
    http_status = 400


class LLMFunctionError(LLMError):
    """Raised when LLM function calling fails."""
    error_code = ErrorCode.LLM_FUNCTION_ERROR


# =============================================================================
# Email Errors
# =============================================================================

class EmailError(BrokerCopilotError):
    """Base class for email-related errors."""
    error_code = ErrorCode.EMAIL_ERROR
    http_status = 500


class EmailSendError(EmailError):
    """Raised when email sending fails."""
    error_code = ErrorCode.EMAIL_SEND_FAILED


class EmailTemplateError(EmailError):
    """Raised when email template processing fails."""
    error_code = ErrorCode.EMAIL_TEMPLATE_ERROR
    http_status = 400


class EmailProviderError(EmailError):
    """Raised when email provider returns an error."""
    error_code = ErrorCode.EMAIL_PROVIDER_ERROR


class EmailNotFoundError(EmailError):
    """Raised when scheduled email is not found."""
    error_code = ErrorCode.EMAIL_NOT_FOUND
    http_status = 404


class EmailAlreadySentError(EmailError):
    """Raised when trying to modify an already sent email."""
    error_code = ErrorCode.EMAIL_ALREADY_SENT
    http_status = 409


# =============================================================================
# PDF Errors
# =============================================================================

class PDFGenerationError(BrokerCopilotError):
    """Base class for PDF generation errors."""
    error_code = ErrorCode.PDF_ERROR
    http_status = 500


class PDFRenderError(PDFGenerationError):
    """Raised when PDF rendering fails."""
    error_code = ErrorCode.PDF_GENERATION_FAILED


class PDFTemplateError(PDFGenerationError):
    """Raised when PDF template processing fails."""
    error_code = ErrorCode.PDF_TEMPLATE_ERROR
    http_status = 400
