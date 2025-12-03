"""
HubSpot CRM Connector
Provides read-only access to HubSpot data for client and deal information.
"""
import os
import httpx
from typing import Dict, Any, List, Optional
from .base import BaseConnector
from ..core.logging import get_logger

logger = get_logger(__name__)


# HubSpot OAuth Configuration
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID", "")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET", "")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/oauth/hubspot/callback")

# HubSpot API base URL
HUBSPOT_API_BASE = "https://api.hubapi.com"


class HubSpotConnector(BaseConnector):
    """
    Connector for HubSpot CRM.
    
    Supports:
    - Companies (Client accounts)
    - Deals (Policies/Renewals)
    - Contacts
    - Notes and Activities
    
    All operations are read-only and return minimal data.
    """
    name = "hubspot"
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(settings)
        self.access_token: Optional[str] = settings.get("access_token")
        self.api_base = HUBSPOT_API_BASE
        self.timeout = settings.get("timeout", 30.0)
        logger.debug(
            "Initialized HubSpot connector",
            extra={"has_token": bool(self.access_token)}
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if not self.access_token:
            logger.error("HubSpot access token not configured")
            raise ValueError("Access token not configured. User must authenticate via OAuth.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def _build_record_link(self, object_type: str, record_id: str, portal_id: str = "") -> str:
        """Build HubSpot deep link for a record."""
        # HubSpot deep links require portal ID
        if portal_id:
            return f"https://app.hubspot.com/contacts/{portal_id}/{object_type}/{record_id}"
        return f"https://app.hubspot.com/contacts/{object_type}/{record_id}"
    
    async def fetch_snippets(self, *, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search across HubSpot objects for matching records.
        """
        logger.info(
            "Fetching HubSpot snippets",
            extra={"query": query, "limit": limit}
        )
        
        if not self.access_token:
            logger.debug("No access token, returning mock company data")
            return self._mock_company_snippets(query, limit)
        
        try:
            # Search companies
            search_body = {
                "query": query,
                "limit": limit,
                "properties": ["name", "industry", "phone", "website", "city", "state"]
            }
            
            logger.debug("Searching HubSpot companies", extra={"query": query})
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/crm/v3/objects/companies/search",
                    headers=self._get_headers(),
                    json=search_body
                )
                response.raise_for_status()
                data = response.json()
            
            results = []
            for record in data.get("results", [])[:limit]:
                props = record.get("properties", {})
                results.append({
                    "id": record["id"],
                    "source": self.name,
                    "type": "Company",
                    "subject": props.get("name", "(No name)"),
                    "timestamp": record.get("createdAt", ""),
                    "snippet": f"Industry: {props.get('industry', 'N/A')} | {props.get('city', '')}, {props.get('state', '')}",
                    "link": self._build_record_link("company", record["id"])
                })
            
            logger.info(
                f"Found {len(results)} HubSpot records",
                extra={"query": query, "result_count": len(results)}
            )
            return results
            
        except httpx.HTTPError as e:
            logger.warning(
                "HubSpot API error, returning mock data",
                extra={"error": str(e), "query": query}
            )
            return self._mock_company_snippets(query, limit)
    
    async def get_record(self, record_id: str) -> Dict[str, Any]:
        """Get a specific company by ID."""
        logger.info(f"Fetching HubSpot record", extra={"record_id": record_id})
        
        if not self.access_token:
            logger.debug("No access token, returning mock company record")
            return self._mock_company_record(record_id)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/crm/v3/objects/companies/{record_id}",
                    headers=self._get_headers(),
                    params={
                        "properties": "name,industry,phone,website,city,state,annualrevenue,description"
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            props = data.get("properties", {})
            logger.info(f"Retrieved HubSpot company record", extra={"record_id": record_id})
            return {
                "id": data["id"],
                "source": self.name,
                "type": "Company",
                "name": props.get("name", ""),
                "industry": props.get("industry", ""),
                "phone": props.get("phone", ""),
                "website": props.get("website", ""),
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "annual_revenue": props.get("annualrevenue", ""),
                "description": props.get("description", ""),
                "link": self._build_record_link("company", data["id"])
            }
            
        except httpx.HTTPError as e:
            logger.warning(
                "HubSpot API error fetching record, returning mock data",
                extra={"record_id": record_id, "error": str(e)}
            )
            return self._mock_company_record(record_id)
    
    async def get_companies(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get client companies."""
        logger.info(f"Fetching HubSpot companies", extra={"limit": limit})
        
        if not self.access_token:
            logger.debug("No access token, returning mock companies")
            return self._mock_companies(limit)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/crm/v3/objects/companies",
                    headers=self._get_headers(),
                    params={
                        "limit": limit,
                        "properties": "name,industry,phone,website,city,state,annualrevenue,createdate"
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            companies = [
                {
                    "id": record["id"],
                    "source": self.name,
                    "name": record.get("properties", {}).get("name", ""),
                    "industry": record.get("properties", {}).get("industry", ""),
                    "phone": record.get("properties", {}).get("phone", ""),
                    "website": record.get("properties", {}).get("website", ""),
                    "city": record.get("properties", {}).get("city", ""),
                    "state": record.get("properties", {}).get("state", ""),
                    "annual_revenue": record.get("properties", {}).get("annualrevenue", 0),
                    "created_date": record.get("properties", {}).get("createdate", ""),
                    "link": self._build_record_link("company", record["id"])
                }
                for record in data.get("results", [])
            ]
            
            logger.info(f"Retrieved {len(companies)} HubSpot companies")
            return companies
            
        except httpx.HTTPError as e:
            logger.warning(
                "HubSpot API error fetching companies, returning mock data",
                extra={"error": str(e)}
            )
            return self._mock_companies(limit)
    
    async def get_deals(
        self,
        stage: Optional[str] = None,
        days_to_close: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get deals (policies/opportunities).
        
        Args:
            stage: Filter by deal stage
            days_to_close: Filter by days until close date
            limit: Maximum records to return
        """
        logger.info(
            "Fetching HubSpot deals",
            extra={
                "stage": stage,
                "days_to_close": days_to_close,
                "limit": limit,
            }
        )
        
        if not self.access_token:
            logger.debug("No access token, returning mock deals")
            return self._mock_deals(limit)
        
        try:
            # Build filter groups if needed
            filters = []
            if stage:
                filters.append({
                    "propertyName": "dealstage",
                    "operator": "EQ",
                    "value": stage
                })
            
            if days_to_close:
                from datetime import datetime, timedelta
                future_date = (datetime.now() + timedelta(days=days_to_close)).strftime("%Y-%m-%d")
                filters.append({
                    "propertyName": "closedate",
                    "operator": "LTE",
                    "value": future_date
                })
            
            search_body = {
                "limit": limit,
                "properties": [
                    "dealname", "amount", "dealstage", "closedate", 
                    "pipeline", "hubspot_owner_id", "description"
                ],
                "sorts": [{"propertyName": "closedate", "direction": "ASCENDING"}]
            }
            
            logger.debug("Searching HubSpot deals", extra={"filter_count": len(filters)})
            
            if filters:
                search_body["filterGroups"] = [{"filters": filters}]
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/crm/v3/objects/deals/search",
                    headers=self._get_headers(),
                    json=search_body
                )
                response.raise_for_status()
                data = response.json()
            
            deals = []
            for record in data.get("results", []):
                props = record.get("properties", {})
                
                # Get associated company
                company_name = await self._get_deal_company(record["id"])
                
                deals.append({
                    "id": record["id"],
                    "source": self.name,
                    "name": props.get("dealname", ""),
                    "amount": float(props.get("amount", 0) or 0),
                    "stage": props.get("dealstage", ""),
                    "close_date": props.get("closedate", ""),
                    "pipeline": props.get("pipeline", ""),
                    "client_name": company_name,
                    "description": props.get("description", ""),
                    "link": self._build_record_link("deal", record["id"])
                })
            
            return deals
            
        except httpx.HTTPError:
            return self._mock_deals(limit)
    
    async def _get_deal_company(self, deal_id: str) -> str:
        """Get the company name associated with a deal."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/crm/v3/objects/deals/{deal_id}/associations/companies",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if results:
                        company_id = results[0].get("id")
                        if company_id:
                            company = await self.get_record(company_id)
                            return company.get("name", "")
            return ""
        except httpx.HTTPError:
            return ""
    
    async def get_renewals(self, days_ahead: int = 90, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get upcoming renewals.
        
        This queries deals with renewal-related properties.
        Adjust based on your HubSpot deal pipeline configuration.
        """
        if not self.access_token:
            return self._mock_renewals(days_ahead, limit)
        
        try:
            from datetime import datetime, timedelta
            
            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            
            search_body = {
                "limit": limit,
                "properties": [
                    "dealname", "amount", "dealstage", "closedate",
                    "pipeline", "hubspot_owner_id", "hs_deal_stage_probability"
                ],
                "filterGroups": [{
                    "filters": [
                        {
                            "propertyName": "closedate",
                            "operator": "LTE",
                            "value": future_date
                        },
                        {
                            "propertyName": "closedate",
                            "operator": "GTE",
                            "value": datetime.now().strftime("%Y-%m-%d")
                        }
                    ]
                }],
                "sorts": [{"propertyName": "closedate", "direction": "ASCENDING"}]
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/crm/v3/objects/deals/search",
                    headers=self._get_headers(),
                    json=search_body
                )
                response.raise_for_status()
                data = response.json()
            
            renewals = []
            for record in data.get("results", []):
                props = record.get("properties", {})
                
                # Get associated company
                company_name = await self._get_deal_company(record["id"])
                
                # Calculate days to expiry
                close_date = props.get("closedate", "")
                days_to_expiry = self._calculate_days_to_date(close_date)
                
                renewals.append({
                    "id": record["id"],
                    "source": self.name,
                    "policy_number": props.get("dealname", ""),
                    "client_name": company_name,
                    "premium_at_risk": float(props.get("amount", 0) or 0),
                    "expiry_date": close_date[:10] if close_date else "",
                    "days_to_expiry": days_to_expiry,
                    "stage": props.get("dealstage", ""),
                    "probability": float(props.get("hs_deal_stage_probability", 0) or 0),
                    "pipeline": props.get("pipeline", ""),
                    "link": self._build_record_link("deal", record["id"])
                })
            
            return renewals
            
        except httpx.HTTPError:
            return self._mock_renewals(days_ahead, limit)
    
    def _calculate_days_to_date(self, date_str: str) -> int:
        """Calculate days from today to a date string."""
        if not date_str:
            return 999
        try:
            from datetime import datetime, date
            # HubSpot dates may include time
            if "T" in date_str:
                date_str = date_str.split("T")[0]
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
            return (target - date.today()).days
        except ValueError:
            return 999
    
    async def get_contacts(self, company_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get contacts, optionally filtered by company."""
        if not self.access_token:
            return self._mock_contacts(limit)
        
        try:
            if company_id:
                # Get contacts associated with company
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.api_base}/crm/v3/objects/companies/{company_id}/associations/contacts",
                        headers=self._get_headers()
                    )
                    
                    if response.status_code != 200:
                        return self._mock_contacts(limit)
                    
                    assoc_data = response.json()
                    contact_ids = [r["id"] for r in assoc_data.get("results", [])]
                
                if not contact_ids:
                    return []
                
                # Fetch contact details
                contacts = []
                for cid in contact_ids[:limit]:
                    response = await client.get(
                        f"{self.api_base}/crm/v3/objects/contacts/{cid}",
                        headers=self._get_headers(),
                        params={"properties": "firstname,lastname,email,phone,jobtitle,company"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        props = data.get("properties", {})
                        contacts.append({
                            "id": data["id"],
                            "source": self.name,
                            "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                            "email": props.get("email", ""),
                            "phone": props.get("phone", ""),
                            "title": props.get("jobtitle", ""),
                            "company": props.get("company", ""),
                            "link": self._build_record_link("contact", data["id"])
                        })
                
                return contacts
            
            else:
                # Get all contacts
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.api_base}/crm/v3/objects/contacts",
                        headers=self._get_headers(),
                        params={
                            "limit": limit,
                            "properties": "firstname,lastname,email,phone,jobtitle,company"
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                
                return [
                    {
                        "id": record["id"],
                        "source": self.name,
                        "name": f"{record.get('properties', {}).get('firstname', '')} {record.get('properties', {}).get('lastname', '')}".strip(),
                        "email": record.get("properties", {}).get("email", ""),
                        "phone": record.get("properties", {}).get("phone", ""),
                        "title": record.get("properties", {}).get("jobtitle", ""),
                        "company": record.get("properties", {}).get("company", ""),
                        "link": self._build_record_link("contact", record["id"])
                    }
                    for record in data.get("results", [])
                ]
            
        except httpx.HTTPError:
            return self._mock_contacts(limit)
    
    async def get_notes_for_deal(self, deal_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get notes/activities associated with a deal."""
        if not self.access_token:
            return self._mock_notes(limit)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Get associated notes
                response = await client.get(
                    f"{self.api_base}/crm/v3/objects/deals/{deal_id}/associations/notes",
                    headers=self._get_headers()
                )
                
                if response.status_code != 200:
                    return []
                
                assoc_data = response.json()
                note_ids = [r["id"] for r in assoc_data.get("results", [])]
            
            if not note_ids:
                return []
            
            # Fetch note details
            notes = []
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for nid in note_ids[:limit]:
                    response = await client.get(
                        f"{self.api_base}/crm/v3/objects/notes/{nid}",
                        headers=self._get_headers(),
                        params={"properties": "hs_note_body,hs_timestamp,hubspot_owner_id"}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        props = data.get("properties", {})
                        notes.append({
                            "id": data["id"],
                            "source": self.name,
                            "content": props.get("hs_note_body", ""),
                            "timestamp": props.get("hs_timestamp", ""),
                            "link": self._build_record_link("note", data["id"])
                        })
            
            return notes
            
        except httpx.HTTPError:
            return self._mock_notes(limit)
    
    # =========================================================================
    # Mock data methods for testing without real OAuth
    # =========================================================================
    
    def _mock_company_snippets(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Return mock company search results."""
        return [
            {
                "id": f"hs-company-{i}",
                "source": self.name,
                "type": "Company",
                "subject": f"Company matching {query} #{i}",
                "timestamp": "2025-12-01T10:00:00Z",
                "snippet": f"Industry: Manufacturing | New York, NY",
                "link": f"https://app.hubspot.com/contacts/company/hs-company-{i}"
            }
            for i in range(1, min(limit + 1, 6))
        ]
    
    def _mock_company_record(self, record_id: str) -> Dict[str, Any]:
        """Return mock company record."""
        return {
            "id": record_id,
            "source": self.name,
            "type": "Company",
            "name": "ACME Corporation",
            "industry": "Manufacturing",
            "phone": "+1-555-0100",
            "website": "https://acme.example.com",
            "city": "New York",
            "state": "NY",
            "annual_revenue": "5000000",
            "description": "Leading manufacturing company",
            "link": f"https://app.hubspot.com/contacts/company/{record_id}"
        }
    
    def _mock_companies(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock companies list."""
        industries = ["Manufacturing", "Technology", "Healthcare", "Finance", "Retail"]
        return [
            {
                "id": f"hs-company-{i}",
                "source": self.name,
                "name": f"Client Company {i}",
                "industry": industries[i % len(industries)],
                "phone": f"+1-555-010{i}",
                "website": f"https://company{i}.example.com",
                "city": "New York",
                "state": "NY",
                "annual_revenue": 1000000 * i,
                "created_date": "2025-01-15T10:00:00Z",
                "link": f"https://app.hubspot.com/contacts/company/hs-company-{i}"
            }
            for i in range(1, min(limit + 1, 11))
        ]
    
    def _mock_deals(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock deals."""
        stages = ["Appointment Scheduled", "Qualified", "Proposal", "Negotiation", "Closed Won"]
        return [
            {
                "id": f"hs-deal-{i}",
                "source": self.name,
                "name": f"Policy Deal {i}",
                "amount": 50000 * i,
                "stage": stages[i % len(stages)],
                "close_date": f"2026-0{min(i, 9)}-15",
                "pipeline": "default",
                "client_name": f"Client Company {i}",
                "description": f"Insurance policy deal for client {i}",
                "link": f"https://app.hubspot.com/contacts/deal/hs-deal-{i}"
            }
            for i in range(1, min(limit + 1, 11))
        ]
    
    def _mock_renewals(self, days_ahead: int, limit: int) -> List[Dict[str, Any]]:
        """Return mock renewals."""
        return [
            {
                "id": f"hs-renewal-{i}",
                "source": self.name,
                "policy_number": f"POL-HS-{1000 + i}",
                "client_name": f"Renewal Client {i}",
                "premium_at_risk": 75000 + (i * 25000),
                "expiry_date": f"2026-01-{10 + i}",
                "days_to_expiry": 30 + (i * 10),
                "stage": "Renewal",
                "probability": 60 + (i * 5),
                "pipeline": "renewals",
                "link": f"https://app.hubspot.com/contacts/deal/hs-renewal-{i}"
            }
            for i in range(1, min(limit + 1, 6))
        ]
    
    def _mock_contacts(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock contacts."""
        titles = ["CFO", "Risk Manager", "CEO", "Operations Director", "VP Finance"]
        return [
            {
                "id": f"hs-contact-{i}",
                "source": self.name,
                "name": f"Contact Person {i}",
                "email": f"contact{i}@example.com",
                "phone": f"+1-555-020{i}",
                "title": titles[i % len(titles)],
                "company": f"Client Company {i}",
                "link": f"https://app.hubspot.com/contacts/contact/hs-contact-{i}"
            }
            for i in range(1, min(limit + 1, 6))
        ]
    
    def _mock_notes(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock notes."""
        return [
            {
                "id": f"hs-note-{i}",
                "source": self.name,
                "content": f"Note {i}: Discussed renewal options with client. They're interested in increasing coverage.",
                "timestamp": f"2025-11-{20 + i}T10:00:00Z",
                "link": f"https://app.hubspot.com/contacts/note/hs-note-{i}"
            }
            for i in range(1, min(limit + 1, 4))
        ]
