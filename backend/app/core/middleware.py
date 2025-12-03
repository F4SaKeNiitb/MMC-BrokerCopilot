"""
Request Middleware for Broker Copilot

Provides:
- Request ID tracking
- Request/Response logging
- Performance metrics
- Error handling middleware
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logging import get_logger, LogContext

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context for logging and tracking.
    
    Adds:
    - Unique request ID (X-Request-ID header)
    - Request timing metrics
    - Structured logging for requests/responses
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        
        # Extract user info if available
        user_id = request.headers.get("X-User-ID", "anonymous")
        
        # Start timing
        start_time = time.perf_counter()
        
        # Set up logging context
        with LogContext(request_id=request_id, user_id=user_id):
            # Log request
            logger.info(
                f"Request started: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                    "client_ip": request.client.host if request.client else "unknown",
                }
            )
            
            try:
                # Process request
                response = await call_next(request)
                
                # Calculate duration
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Log response
                log_level = "info" if response.status_code < 400 else "warning"
                getattr(logger, log_level)(
                    f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )
                
                # Add headers to response
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
                
                return response
                
            except Exception as e:
                # Calculate duration even on error
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                logger.error(
                    f"Request failed: {request.method} {request.url.path}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True
                )
                raise
