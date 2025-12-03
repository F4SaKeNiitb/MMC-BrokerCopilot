from typing import Dict, Any, List
from abc import ABC, abstractmethod

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
    name: str = "base"

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings

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
