"""
Salesforce CRM Connector
Provides read-only access to Salesforce data for policy and client information.
"""
import os
import httpx
from typing import Dict, Any, List, Optional
from .base import BaseConnector
from ..core.logging import get_logger

logger = get_logger(__name__)


# Salesforce OAuth Configuration
SF_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID", "")
SF_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET", "")
SF_REDIRECT_URI = os.getenv("SALESFORCE_REDIRECT_URI", "http://localhost:8000/oauth/salesforce/callback")

# Salesforce API version
SF_API_VERSION = "v59.0"


class SalesforceConnector(BaseConnector):
    """
    Connector for Salesforce CRM.
    
    Supports:
    - Account (Client) lookup
    - Opportunity (Policy/Renewal) data
    - Contact information
    - Custom objects for insurance-specific data
    
    All operations are read-only and return minimal data (metadata + snippets).
    """
    name = "salesforce"
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(settings)
        self.access_token: Optional[str] = settings.get("access_token")
        self.instance_url: Optional[str] = settings.get("instance_url")
        self.timeout = settings.get("timeout", 30.0)
        self.api_version = settings.get("api_version", SF_API_VERSION)
        logger.debug(
            "Initialized Salesforce connector",
            extra={
                "instance_url": self.instance_url,
                "api_version": self.api_version,
                "has_token": bool(self.access_token),
            }
        )
    
    @property
    def api_base(self) -> str:
        """Get the API base URL for this Salesforce instance."""
        if not self.instance_url:
            logger.error("Salesforce instance URL not configured")
            raise ValueError("Salesforce instance URL not configured")
        return f"{self.instance_url}/services/data/{self.api_version}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if not self.access_token:
            logger.error("Salesforce access token not configured")
            raise ValueError("Access token not configured. User must authenticate via OAuth.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def _build_record_link(self, record_id: str) -> str:
        """Build Salesforce deep link for a record."""
        if self.instance_url:
            return f"{self.instance_url}/{record_id}"
        return f"https://login.salesforce.com/{record_id}"
    
    async def fetch_snippets(self, *, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search across Salesforce objects for matching records.
        Uses SOSL (Salesforce Object Search Language) for full-text search.
        """
        logger.info(
            "Fetching Salesforce snippets",
            extra={"query": query, "limit": limit}
        )
        
        if not self.access_token:
            logger.debug("No access token, returning mock data")
            return self._mock_account_snippets(query, limit)
        
        try:
            # SOSL search across Account and Opportunity
            sosl_query = f"FIND {{{query}}} IN ALL FIELDS RETURNING Account(Id, Name, Industry, Phone, Website LIMIT {limit}), Opportunity(Id, Name, Amount, StageName, CloseDate LIMIT {limit})"
            
            logger.debug(f"Executing SOSL query", extra={"sosl": sosl_query})
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/search/",
                    headers=self._get_headers(),
                    params={"q": sosl_query}
                )
                response.raise_for_status()
                data = response.json()
            
            results = []
            for record in data.get("searchRecords", [])[:limit]:
                obj_type = record.get("attributes", {}).get("type", "Unknown")
                results.append({
                    "id": record["Id"],
                    "source": self.name,
                    "type": obj_type,
                    "subject": record.get("Name", "(No name)"),
                    "timestamp": record.get("CloseDate", ""),
                    "snippet": self._build_snippet(record, obj_type),
                    "link": self._build_record_link(record["Id"])
                })
            
            logger.info(
                f"Found {len(results)} Salesforce records",
                extra={"query": query, "result_count": len(results)}
            )
            return results
            
        except httpx.HTTPError as e:
            logger.warning(
                f"Salesforce API error, returning mock data",
                extra={"error": str(e), "query": query}
            )
            return self._mock_account_snippets(query, limit)
    
    def _build_snippet(self, record: Dict, obj_type: str) -> str:
        """Build a snippet from record fields."""
        if obj_type == "Account":
            return f"Industry: {record.get('Industry', 'N/A')} | Phone: {record.get('Phone', 'N/A')}"
        elif obj_type == "Opportunity":
            amount = record.get('Amount', 0)
            return f"Amount: ${amount:,.2f} | Stage: {record.get('StageName', 'N/A')}"
        return ""
    
    async def get_record(self, record_id: str) -> Dict[str, Any]:
        """Get a specific record by ID."""
        logger.info(f"Fetching Salesforce record", extra={"record_id": record_id})
        
        if not self.access_token:
            logger.debug("No access token, returning mock record")
            return self._mock_account_record(record_id)
        
        try:
            # Try to determine object type and fetch
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # First try Account
                logger.debug(f"Trying to fetch as Account: {record_id}")
                response = await client.get(
                    f"{self.api_base}/sobjects/Account/{record_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Retrieved Account record", extra={"record_id": record_id})
                    return {
                        "id": data["Id"],
                        "source": self.name,
                        "type": "Account",
                        "name": data.get("Name", ""),
                        "industry": data.get("Industry", ""),
                        "phone": data.get("Phone", ""),
                        "website": data.get("Website", ""),
                        "link": self._build_record_link(data["Id"])
                    }
                
                # Try Opportunity
                logger.debug(f"Trying to fetch as Opportunity: {record_id}")
                response = await client.get(
                    f"{self.api_base}/sobjects/Opportunity/{record_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Retrieved Opportunity record", extra={"record_id": record_id})
                    return {
                        "id": data["Id"],
                        "source": self.name,
                        "type": "Opportunity",
                        "name": data.get("Name", ""),
                        "amount": data.get("Amount", 0),
                        "stage": data.get("StageName", ""),
                        "close_date": data.get("CloseDate", ""),
                        "link": self._build_record_link(data["Id"])
                    }
            
            logger.warning(f"Salesforce record not found", extra={"record_id": record_id})
            return {"error": "Record not found"}
            
        except httpx.HTTPError as e:
            logger.error(
                f"Salesforce API error fetching record",
                extra={"record_id": record_id, "error": str(e)}
            )
            return self._mock_account_record(record_id)
    
    async def get_accounts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get client accounts."""
        logger.info(f"Fetching Salesforce accounts", extra={"limit": limit})
        
        if not self.access_token:
            logger.debug("No access token, returning mock accounts")
            return self._mock_accounts(limit)
        
        try:
            query = f"SELECT Id, Name, Industry, Phone, Website, BillingCity, BillingState, AnnualRevenue, CreatedDate FROM Account ORDER BY CreatedDate DESC LIMIT {limit}"
            
            logger.debug("Executing SOQL query for accounts", extra={"soql": query})
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/query/",
                    headers=self._get_headers(),
                    params={"q": query}
                )
                response.raise_for_status()
                data = response.json()
            
            accounts = [
                {
                    "id": record["Id"],
                    "source": self.name,
                    "name": record.get("Name", ""),
                    "industry": record.get("Industry", ""),
                    "phone": record.get("Phone", ""),
                    "website": record.get("Website", ""),
                    "city": record.get("BillingCity", ""),
                    "state": record.get("BillingState", ""),
                    "annual_revenue": record.get("AnnualRevenue", 0),
                    "created_date": record.get("CreatedDate", ""),
                    "link": self._build_record_link(record["Id"])
                }
                for record in data.get("records", [])
            ]
            
            logger.info(f"Retrieved {len(accounts)} Salesforce accounts")
            return accounts
            
        except httpx.HTTPError as e:
            logger.warning(
                f"Salesforce API error fetching accounts, returning mock data",
                extra={"error": str(e)}
            )
            return self._mock_accounts(limit)
    
    async def get_opportunities(
        self,
        stage: Optional[str] = None,
        days_to_close: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get opportunities (policies/renewals).
        
        Args:
            stage: Filter by stage name
            days_to_close: Filter by days until close date
            limit: Maximum records to return
        """
        logger.info(
            "Fetching Salesforce opportunities",
            extra={
                "stage": stage,
                "days_to_close": days_to_close,
                "limit": limit,
            }
        )
        
        if not self.access_token:
            logger.debug("No access token, returning mock opportunities")
            return self._mock_opportunities(limit)
        
        try:
            conditions = []
            if stage:
                conditions.append(f"StageName = '{stage}'")
            if days_to_close:
                conditions.append(f"CloseDate = NEXT_N_DAYS:{days_to_close}")
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"""
                SELECT Id, Name, Amount, StageName, CloseDate, Probability, 
                       Account.Name, Account.Id, OwnerId, Owner.Name, 
                       Description, CreatedDate
                FROM Opportunity 
                {where_clause}
                ORDER BY CloseDate ASC 
                LIMIT {limit}
            """
            
            logger.debug("Executing SOQL query for opportunities")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/query/",
                    headers=self._get_headers(),
                    params={"q": query}
                )
                response.raise_for_status()
                data = response.json()
            
            opportunities = [
                {
                    "id": record["Id"],
                    "source": self.name,
                    "name": record.get("Name", ""),
                    "amount": record.get("Amount", 0),
                    "stage": record.get("StageName", ""),
                    "close_date": record.get("CloseDate", ""),
                    "probability": record.get("Probability", 0),
                    "client_name": record.get("Account", {}).get("Name", "") if record.get("Account") else "",
                    "client_id": record.get("Account", {}).get("Id", "") if record.get("Account") else "",
                    "owner_name": record.get("Owner", {}).get("Name", "") if record.get("Owner") else "",
                    "description": record.get("Description", ""),
                    "link": self._build_record_link(record["Id"])
                }
                for record in data.get("records", [])
            ]
            
            logger.info(
                f"Retrieved {len(opportunities)} Salesforce opportunities",
                extra={"stage": stage, "days_to_close": days_to_close}
            )
            return opportunities
            
        except httpx.HTTPError as e:
            logger.warning(
                "Salesforce API error fetching opportunities, returning mock data",
                extra={"error": str(e)}
            )
            return self._mock_opportunities(limit)
    
    async def get_renewals(self, days_ahead: int = 90, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get upcoming renewals.
        
        This queries opportunities with renewal-related stages or custom renewal objects.
        Adjust the query based on your Salesforce schema.
        """
        logger.info(
            "Fetching Salesforce renewals",
            extra={"days_ahead": days_ahead, "limit": limit}
        )
        
        if not self.access_token:
            logger.debug("No access token, returning mock renewals")
            return self._mock_renewals(days_ahead, limit)
        
        try:
            # Query for renewal opportunities
            query = f"""
                SELECT Id, Name, Amount, StageName, CloseDate, Probability,
                       Account.Name, Account.Id, Owner.Name,
                       Description, Type
                FROM Opportunity
                WHERE CloseDate = NEXT_N_DAYS:{days_ahead}
                  AND (Type = 'Renewal' OR StageName LIKE '%Renewal%')
                ORDER BY CloseDate ASC
                LIMIT {limit}
            """
            
            logger.debug("Executing SOQL query for renewals")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/query/",
                    headers=self._get_headers(),
                    params={"q": query}
                )
                response.raise_for_status()
                data = response.json()
            
            renewals = []
            for record in data.get("records", []):
                # Calculate days to expiry
                close_date = record.get("CloseDate", "")
                days_to_expiry = self._calculate_days_to_date(close_date)
                
                renewals.append({
                    "id": record["Id"],
                    "source": self.name,
                    "policy_number": record.get("Name", ""),
                    "client_name": record.get("Account", {}).get("Name", "") if record.get("Account") else "",
                    "client_id": record.get("Account", {}).get("Id", "") if record.get("Account") else "",
                    "premium_at_risk": record.get("Amount", 0),
                    "expiry_date": close_date,
                    "days_to_expiry": days_to_expiry,
                    "stage": record.get("StageName", ""),
                    "probability": record.get("Probability", 0),
                    "assignee": record.get("Owner", {}).get("Name", "") if record.get("Owner") else "",
                    "link": self._build_record_link(record["Id"])
                })
            
            logger.info(
                f"Retrieved {len(renewals)} Salesforce renewals",
                extra={"days_ahead": days_ahead}
            )
            return renewals
            
        except httpx.HTTPError as e:
            logger.warning(
                "Salesforce API error fetching renewals, returning mock data",
                extra={"error": str(e)}
            )
            return self._mock_renewals(days_ahead, limit)
    
    def _calculate_days_to_date(self, date_str: str) -> int:
        """Calculate days from today to a date string."""
        if not date_str:
            return 999
        try:
            from datetime import datetime, date
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
            return (target - date.today()).days
        except ValueError:
            return 999
    
    async def get_contacts_for_account(self, account_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get contacts associated with an account."""
        logger.debug(
            "Fetching contacts for Salesforce account",
            extra={"account_id": account_id, "limit": limit}
        )
        
        if not self.access_token:
            logger.debug("No access token, returning mock contacts")
            return self._mock_contacts(limit)
        
        try:
            query = f"""
                SELECT Id, Name, Email, Phone, Title, Department
                FROM Contact
                WHERE AccountId = '{account_id}'
                ORDER BY CreatedDate DESC
                LIMIT {limit}
            """
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/query/",
                    headers=self._get_headers(),
                    params={"q": query}
                )
                response.raise_for_status()
                data = response.json()
            
            return [
                {
                    "id": record["Id"],
                    "source": self.name,
                    "name": record.get("Name", ""),
                    "email": record.get("Email", ""),
                    "phone": record.get("Phone", ""),
                    "title": record.get("Title", ""),
                    "department": record.get("Department", ""),
                    "link": self._build_record_link(record["Id"])
                }
                for record in data.get("records", [])
            ]
            
        except httpx.HTTPError:
            return self._mock_contacts(limit)
    
    # =========================================================================
    # Mock data methods for testing without real OAuth
    # =========================================================================
    
    def _mock_account_snippets(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Return mock account search results."""
        return [
            {
                "id": f"001{i}000000mock",
                "source": self.name,
                "type": "Account",
                "subject": f"ACME Corp {query} #{i}",
                "timestamp": "2025-12-01",
                "snippet": f"Industry: Manufacturing | Phone: +1-555-010{i}",
                "link": f"https://yourinstance.salesforce.com/001{i}000000mock"
            }
            for i in range(1, min(limit + 1, 6))
        ]
    
    def _mock_account_record(self, record_id: str) -> Dict[str, Any]:
        """Return mock account record."""
        return {
            "id": record_id,
            "source": self.name,
            "type": "Account",
            "name": "ACME Corporation",
            "industry": "Manufacturing",
            "phone": "+1-555-0100",
            "website": "https://acme.example.com",
            "link": f"https://yourinstance.salesforce.com/{record_id}"
        }
    
    def _mock_accounts(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock accounts list."""
        return [
            {
                "id": f"001{i}000000mock",
                "source": self.name,
                "name": f"Client Company {i}",
                "industry": ["Manufacturing", "Technology", "Healthcare", "Finance"][i % 4],
                "phone": f"+1-555-010{i}",
                "website": f"https://company{i}.example.com",
                "city": "New York",
                "state": "NY",
                "annual_revenue": 1000000 * i,
                "created_date": "2025-01-15T10:00:00Z",
                "link": f"https://yourinstance.salesforce.com/001{i}000000mock"
            }
            for i in range(1, min(limit + 1, 11))
        ]
    
    def _mock_opportunities(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock opportunities."""
        stages = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won"]
        return [
            {
                "id": f"006{i}000000mock",
                "source": self.name,
                "name": f"Opportunity {i}",
                "amount": 50000 * i,
                "stage": stages[i % len(stages)],
                "close_date": f"2026-0{min(i, 9)}-15",
                "probability": 20 * (i % 5 + 1),
                "client_name": f"Client {i}",
                "client_id": f"001{i}000000mock",
                "owner_name": "John Broker",
                "description": f"Policy opportunity for client {i}",
                "link": f"https://yourinstance.salesforce.com/006{i}000000mock"
            }
            for i in range(1, min(limit + 1, 11))
        ]
    
    def _mock_renewals(self, days_ahead: int, limit: int) -> List[Dict[str, Any]]:
        """Return mock renewals."""
        return [
            {
                "id": f"006{i}000000renew",
                "source": self.name,
                "policy_number": f"POL-{1000 + i}",
                "client_name": f"Renewal Client {i}",
                "client_id": f"001{i}000000mock",
                "premium_at_risk": 75000 + (i * 25000),
                "expiry_date": f"2026-01-{10 + i}",
                "days_to_expiry": 30 + (i * 10),
                "stage": "Renewal",
                "probability": 60 + (i * 5),
                "assignee": "Jane Broker",
                "link": f"https://yourinstance.salesforce.com/006{i}000000renew"
            }
            for i in range(1, min(limit + 1, 6))
        ]
    
    def _mock_contacts(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock contacts."""
        return [
            {
                "id": f"003{i}000000mock",
                "source": self.name,
                "name": f"Contact Person {i}",
                "email": f"contact{i}@example.com",
                "phone": f"+1-555-020{i}",
                "title": ["CFO", "Risk Manager", "CEO", "Operations Director"][i % 4],
                "department": ["Finance", "Operations", "Executive", "Risk"][i % 4],
                "link": f"https://yourinstance.salesforce.com/003{i}000000mock"
            }
            for i in range(1, min(limit + 1, 6))
        ]
