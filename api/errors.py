# api/errors.py
"""
Standardized API Error Responses

Provides consistent error formats across all API endpoints.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import uuid

from log_manager import get_logger

_logger = get_logger("api_errors")


class ErrorCode(str, Enum):
    """Standard error codes"""
    # Client errors (4xx)
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RAG_ERROR = "RAG_ERROR"
    PIPELINE_ERROR = "PIPELINE_ERROR"
    TIMEOUT = "TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorType(str, Enum):
    """Error types"""
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: ErrorCode
    message: str
    type: ErrorType
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True


class APIError(HTTPException):
    """
    Custom API error with standardized format.

    Usage:
        raise APIError(
            status_code=400,
            error_code=ErrorCode.INVALID_INPUT,
            message="Question cannot be empty",
            details={"field": "question"}
        )
    """

    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        error_type: Optional[ErrorType] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        # Auto-determine error type from status code if not provided
        if error_type is None:
            if status_code == 401:
                error_type = ErrorType.AUTHENTICATION_ERROR
            elif status_code == 429:
                error_type = ErrorType.RATE_LIMIT_ERROR
            elif 400 <= status_code < 500:
                error_type = ErrorType.VALIDATION_ERROR
            else:
                error_type = ErrorType.INTERNAL_ERROR

        # Generate request ID if not provided
        if request_id is None:
            request_id = f"req_{uuid.uuid4().hex[:16]}"

        self.error_detail = ErrorDetail(
            code=error_code,
            message=message,
            type=error_type,
            request_id=request_id,
            details=details
        )

        super().__init__(
            status_code=status_code,
            detail=self.error_detail.dict()
        )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handle APIError exceptions and return standardized JSON response.

    Response format:
    {
        "error": {
            "code": "INVALID_INPUT",
            "message": "Question cannot be empty",
            "type": "validation_error",
            "request_id": "req_abc123",
            "details": {"field": "question"}
        }
    }
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_detail.dict()},
        headers={
            "X-Request-ID": exc.error_detail.request_id or "unknown",
            "X-Error-Code": exc.error_detail.code,
        }
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions with standardized format.

    Prevents leaking internal implementation details to clients.
    """
    request_id = f"req_{uuid.uuid4().hex[:16]}"

    _logger.error(f"{request_id}: {type(exc).__name__}: {str(exc)}")

    error_detail = ErrorDetail(
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred. Please try again later.",
        type=ErrorType.INTERNAL_ERROR,
        request_id=request_id,
        details=None  # Don't leak internal details
    )

    return JSONResponse(
        status_code=500,
        content={"error": error_detail.dict()},
        headers={
            "X-Request-ID": request_id,
            "X-Error-Code": ErrorCode.INTERNAL_ERROR,
        }
    )


# Convenience functions for common errors

def raise_validation_error(message: str, field: Optional[str] = None) -> None:
    """Raise a validation error"""
    details = {"field": field} if field else None
    raise APIError(
        status_code=400,
        error_code=ErrorCode.VALIDATION_ERROR,
        message=message,
        error_type=ErrorType.VALIDATION_ERROR,
        details=details
    )


def raise_rate_limit_error(retry_after: int) -> None:
    """Raise a rate limit error"""
    raise APIError(
        status_code=429,
        error_code=ErrorCode.RATE_LIMITED,
        message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
        error_type=ErrorType.RATE_LIMIT_ERROR,
        details={"retry_after": retry_after}
    )


def raise_model_unavailable(provider: str, model: str) -> None:
    """Raise a model unavailable error"""
    raise APIError(
        status_code=503,
        error_code=ErrorCode.MODEL_UNAVAILABLE,
        message=f"LLM provider '{provider}' model '{model}' is currently unavailable.",
        error_type=ErrorType.INTERNAL_ERROR,
        details={"provider": provider, "model": model}
    )


def raise_pipeline_error(stage: str, error_message: str) -> None:
    """Raise a pipeline error"""
    raise APIError(
        status_code=500,
        error_code=ErrorCode.PIPELINE_ERROR,
        message=f"Pipeline error at stage '{stage}': {error_message}",
        error_type=ErrorType.INTERNAL_ERROR,
        details={"stage": stage}
    )


def raise_internal_error(
    stage: str,
    exc: Exception,
    *,
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
    status_code: int = 500,
) -> None:
    """
    Log the real exception server-side and raise a SANITIZED client error.

    Routers previously did `message=f"...: {str(e)}"`, leaking internal
    implementation details (stack/exception text, sometimes secrets) to the
    client. This helper keeps the real cause in server logs (correlatable via
    request_id) while the client only sees a generic message + request_id.
    """
    request_id = f"req_{uuid.uuid4().hex[:16]}"
    _logger.error("%s: [%s] %s: %s", request_id, stage, type(exc).__name__, str(exc))
    raise APIError(
        status_code=status_code,
        error_code=error_code,
        message="An internal error occurred while processing the request.",
        request_id=request_id,
        details={"stage": stage},
    )
