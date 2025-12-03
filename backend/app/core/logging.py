"""
Centralized Logging Configuration for Broker Copilot

Provides structured logging with:
- Configurable log levels
- JSON and human-readable formatters
- Request context tracking
- Performance metrics
- Sensitive data masking
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Union
from contextvars import ContextVar
from functools import wraps
import time

# Context variable for request-scoped data
_request_context: ContextVar[Dict[str, Any]] = ContextVar('request_context', default={})


class LogContext:
    """
    Context manager for adding contextual information to log records.
    
    Usage:
        with LogContext(request_id="abc123", user_id="user456"):
            logger.info("Processing request")
    """
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self._token = None
    
    def __enter__(self):
        current = _request_context.get().copy()
        current.update(self.context)
        self._token = _request_context.set(current)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            _request_context.reset(self._token)
        return False
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get a value from the current context."""
        return _request_context.get().get(key, default)
    
    @staticmethod
    def get_all() -> Dict[str, Any]:
        """Get all context values."""
        return _request_context.get().copy()
    
    @staticmethod
    def set(**kwargs):
        """Set context values without using a context manager."""
        current = _request_context.get().copy()
        current.update(kwargs)
        return _request_context.set(current)


class SensitiveDataFilter(logging.Filter):
    """
    Filter to mask sensitive data in log records.
    
    Masks:
    - Access tokens
    - Refresh tokens
    - API keys
    - Passwords
    - Email addresses (partial)
    """
    
    SENSITIVE_PATTERNS = [
        ('access_token', '***ACCESS_TOKEN***'),
        ('refresh_token', '***REFRESH_TOKEN***'),
        ('api_key', '***API_KEY***'),
        ('password', '***PASSWORD***'),
        ('client_secret', '***CLIENT_SECRET***'),
        ('authorization', '***AUTH***'),
        ('bearer', '***BEARER***'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            msg_lower = record.msg.lower()
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                if pattern in msg_lower:
                    # Mask the value that follows the pattern
                    record.msg = self._mask_value(record.msg, pattern, replacement)
        return True
    
    @staticmethod
    def _mask_value(msg: str, pattern: str, replacement: str) -> str:
        """Mask sensitive values in the message."""
        import re
        # Match pattern followed by various separators and values
        patterns = [
            rf'({pattern}[\s=:]+)[^\s,\}}\]]+',  # key=value or key: value
            rf'("{pattern}"[\s:]+)"[^"]*"',  # JSON string value
        ]
        for p in patterns:
            msg = re.sub(p, rf'\g<1>{replacement}', msg, flags=re.IGNORECASE)
        return msg


class ContextualFilter(logging.Filter):
    """Add request context to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        context = _request_context.get()
        for key, value in context.items():
            setattr(record, key, value)
        
        # Set defaults for missing context
        if not hasattr(record, 'request_id'):
            record.request_id = 'N/A'
        if not hasattr(record, 'user_id'):
            record.user_id = 'N/A'
        
        return True


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Ideal for log aggregation systems like ELK, Datadog, etc.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add context fields
        context = _request_context.get()
        if context:
            log_data['context'] = context
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info),
            }
        
        # Add extra fields
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__dict__ and not k.startswith('_')
            and k not in ['message', 'args', 'exc_info', 'exc_text', 'stack_info', 'msg']
        }
        if extras:
            log_data['extra'] = extras
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Human-readable formatter with colors for console output.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, fmt: str = None, use_colors: bool = True):
        super().__init__(fmt or '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s')
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        # Add context to message
        context = _request_context.get()
        if context:
            context_str = ' | '.join(f'{k}={v}' for k, v in context.items())
            record.msg = f"[{context_str}] {record.msg}"
        
        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{self.BOLD}{record.levelname}{self.RESET}"
        
        formatted = super().format(record)
        
        return formatted


def configure_logging(
    level: Union[str, int] = None,
    json_format: bool = None,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure global logging settings.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting (auto-detected if None)
        log_file: Optional file path for logging
    """
    # Determine settings from environment or arguments
    level = level or os.getenv('LOG_LEVEL', 'INFO')
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    # Auto-detect JSON format based on environment
    if json_format is None:
        json_format = os.getenv('LOG_FORMAT', 'text').lower() == 'json'
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())
    
    # Add filters
    console_handler.addFilter(SensitiveDataFilter())
    console_handler.addFilter(ContextualFilter())
    
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        file_handler.addFilter(SensitiveDataFilter())
        file_handler.addFilter(ContextualFilter())
        root_logger.addHandler(file_handler)
    
    # Set levels for noisy third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the standard configuration.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Hello, world!")
    """
    return logging.getLogger(name)


def log_function_call(logger: logging.Logger = None, level: int = logging.DEBUG):
    """
    Decorator to log function entry, exit, and execution time.
    
    Usage:
        @log_function_call()
        def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__qualname__
            
            # Log entry
            logger.log(level, f"Entering {func_name}")
            
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.log(level, f"Exiting {func_name} (took {elapsed:.2f}ms)")
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"Exception in {func_name} after {elapsed:.2f}ms: {type(e).__name__}: {e}",
                    exc_info=True
                )
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__qualname__
            
            # Log entry
            logger.log(level, f"Entering {func_name}")
            
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.log(level, f"Exiting {func_name} (took {elapsed:.2f}ms)")
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"Exception in {func_name} after {elapsed:.2f}ms: {type(e).__name__}: {e}",
                    exc_info=True
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    
    return decorator


def log_exception(
    logger: logging.Logger,
    exception: Exception,
    message: str = "An error occurred",
    include_traceback: bool = True,
    extra: Dict[str, Any] = None
) -> None:
    """
    Log an exception with context and optional traceback.
    
    Args:
        logger: Logger instance
        exception: The exception to log
        message: Custom message prefix
        include_traceback: Whether to include full traceback
        extra: Additional context to log
    """
    exc_type = type(exception).__name__
    exc_msg = str(exception)
    
    log_message = f"{message}: [{exc_type}] {exc_msg}"
    
    if extra:
        log_message += f" | Context: {json.dumps(extra, default=str)}"
    
    if include_traceback:
        logger.error(log_message, exc_info=True)
    else:
        logger.error(log_message)


# Initialize logging on module import with defaults
configure_logging()
