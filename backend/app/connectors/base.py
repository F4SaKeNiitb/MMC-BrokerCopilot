"""
Base Connector Module

Defines the abstract base class for all data connectors with standardized
error handling and logging.
"""
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from ..core.logging import get_logger
from ..core.exceptions import ConnectorError, ConnectorAuthRequiredError

logger = get_logger(__name__)


class ConnectorResult(Dict):
    """Standardized snippet result.
    Fields:
    - id: record id
    - source: connector name
    - subject: short subject/title
    - timestamp: ISO timestamp string
    - snippet: short text snippet
    - link: deep link to original record (provenance)
    """
    pass


class BaseConnector(ABC):
    """
    Abstract base class for all data connectors.
    
    Provides:
    - Standardized interface for data fetching
    - Logging integration
    - Error handling patterns
    """
    name: str = "base"

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.logger = get_logger(f"{__name__}.{self.name}")

    @abstractmethod
    async def fetch_snippets(self, *, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch lightweight metadata snippets matching query.
        Return list of dicts with keys: id, subject, timestamp, snippet, link
        """
        raise NotImplementedError()

    @abstractmethod
    async def get_record(self, record_id: str) -> Dict[str, Any]:
        """Fetch a specific record details (minimal fields)."""
        raise NotImplementedError()
    
    def _log_request(self, operation: str, **kwargs):
        """Log an API request."""
        self.logger.debug(f"{operation} - {kwargs}")
    
    def _log_response(self, operation: str, count: int = None, **kwargs):
        """Log an API response."""
        if count is not None:
            self.logger.debug(f"{operation} returned {count} results")
        else:
            self.logger.debug(f"{operation} completed - {kwargs}")
    
    def _log_error(self, operation: str, error: Exception, **kwargs):
        """Log an API error."""
        self.logger.error(f"{operation} failed: {type(error).__name__}: {error}", extra=kwargs)
