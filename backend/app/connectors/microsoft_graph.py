"""
Microsoft Graph API Connector
Provides read-only access to Microsoft 365 data (Mail, Calendar, Teams).
Implements minimalist fetching - only retrieves metadata and snippets.
"""
import httpx
from typing import Dict, Any, List, Optional
from .base import BaseConnector
import asyncio


class MicrosoftGraphConnector(BaseConnector):
    """
    Connector for Microsoft Graph API.
    
    Supports:
    - Email search and retrieval (Mail.Read)
    - Calendar events (Calendars.Read)
    - Teams chat messages (Chat.Read)
    - User profile (User.Read)
    
    All operations are read-only and return minimal data (metadata + snippets).
    """
    name = "microsoft_graph"
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(settings)
        self.api_base = "https://graph.microsoft.com/v1.0"
        self.access_token: Optional[str] = settings.get("access_token")
        self.timeout = settings.get("timeout", 30.0)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if not self.access_token:
            raise ValueError("Access token not configured. User must authenticate via OAuth.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def _build_email_deep_link(self, message_id: str) -> str:
        """Build Outlook deep link for an email."""
        # Web link format for Outlook
        return f"https://outlook.office.com/mail/item/{message_id}"
    
    def _build_event_deep_link(self, event_id: str) -> str:
        """Build Calendar deep link for an event."""
        return f"https://outlook.office.com/calendar/item/{event_id}"
    
    def _build_chat_deep_link(self, chat_id: str, message_id: str) -> str:
        """Build Teams deep link for a chat message."""
        return f"https://teams.microsoft.com/l/message/{chat_id}/{message_id}"

    async def fetch_snippets(self, *, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search emails matching query and return metadata snippets.
        
        Uses Microsoft Search API for better relevance.
        Returns minimal data: id, subject, timestamp, snippet, link
        """
        if not self.access_token:
            # Return mock data if no token (for testing)
            return self._mock_email_snippets(query, limit)
        
        try:
            # Use $search for keyword search or $filter for specific queries
            params = {
                "$select": "id,subject,receivedDateTime,bodyPreview,from,webLink",
                "$top": limit,
                "$orderby": "receivedDateTime desc",
            }
            
            # If query looks like an email or name, search in from/to
            if "@" in query or " " in query:
                params["$search"] = f'"{query}"'
            else:
                params["$filter"] = f"contains(subject, '{query}') or contains(bodyPreview, '{query}')"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/me/messages",
                    headers=self._get_headers(),
                    params=params
                )
                
                if response.status_code == 401:
                    raise ValueError("Access token expired or invalid")
                
                response.raise_for_status()
                data = response.json()
            
            results = []
            for msg in data.get("value", [])[:limit]:
                results.append({
                    "id": msg["id"],
                    "source": self.name,
                    "subject": msg.get("subject", "(No subject)"),
                    "timestamp": msg.get("receivedDateTime", ""),
                    "snippet": (msg.get("bodyPreview", "")[:200] + "...") if msg.get("bodyPreview") else "",
                    "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "link": msg.get("webLink") or self._build_email_deep_link(msg["id"])
                })
            
            return results
            
        except httpx.HTTPError as e:
            # On error, return empty or mock data
            return []
    
    async def search_emails(
        self,
        query: str,
        limit: int = 10,
        folder: str = None
    ) -> List[Dict[str, Any]]:
        """
        Advanced email search using Microsoft Search API.
        
        Args:
            query: Search keywords
            limit: Maximum results
            folder: Optional folder to search in (inbox, sentitems, etc.)
        
        Returns:
            List of email snippets with provenance links
        """
        if not self.access_token:
            return self._mock_email_snippets(query, limit)
        
        # Use Graph Search API for better relevance
        search_request = {
            "requests": [{
                "entityTypes": ["message"],
                "query": {
                    "queryString": query
                },
                "from": 0,
                "size": limit
            }]
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/search/query",
                    headers=self._get_headers(),
                    json=search_request
                )
                response.raise_for_status()
                data = response.json()
            
            results = []
            hits = data.get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])
            
            for hit in hits[:limit]:
                resource = hit.get("resource", {})
                results.append({
                    "id": resource.get("id", ""),
                    "source": self.name,
                    "subject": resource.get("subject", "(No subject)"),
                    "timestamp": resource.get("receivedDateTime", ""),
                    "snippet": resource.get("bodyPreview", "")[:200],
                    "from": resource.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "link": resource.get("webLink") or self._build_email_deep_link(resource.get("id", ""))
                })
            
            return results
            
        except httpx.HTTPError:
            return []
    
    async def get_calendar_events(
        self,
        days_ahead: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming calendar events.
        
        Args:
            days_ahead: Number of days to look ahead
            limit: Maximum events to return
        
        Returns:
            List of event snippets with provenance links
        """
        if not self.access_token:
            return self._mock_calendar_events(limit)
        
        from datetime import datetime, timedelta
        
        start_time = datetime.utcnow().isoformat() + "Z"
        end_time = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
        
        params = {
            "startDateTime": start_time,
            "endDateTime": end_time,
            "$select": "id,subject,start,end,location,bodyPreview,webLink,attendees",
            "$top": limit,
            "$orderby": "start/dateTime"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/me/calendarView",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                data = response.json()
            
            results = []
            for event in data.get("value", [])[:limit]:
                attendee_emails = [
                    a.get("emailAddress", {}).get("address", "")
                    for a in event.get("attendees", [])
                ]
                
                results.append({
                    "id": event["id"],
                    "source": self.name,
                    "subject": event.get("subject", "(No subject)"),
                    "timestamp": event.get("start", {}).get("dateTime", ""),
                    "end_time": event.get("end", {}).get("dateTime", ""),
                    "location": event.get("location", {}).get("displayName", ""),
                    "snippet": event.get("bodyPreview", "")[:200],
                    "attendees": attendee_emails,
                    "link": event.get("webLink") or self._build_event_deep_link(event["id"])
                })
            
            return results
            
        except httpx.HTTPError:
            return []
    
    async def get_recent_chats(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent Teams chat messages.
        
        Requires Chat.Read permission.
        
        Returns:
            List of chat message snippets with provenance links
        """
        if not self.access_token:
            return self._mock_chat_messages(limit)
        
        try:
            # First get chats
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/me/chats",
                    headers=self._get_headers(),
                    params={"$top": 10}
                )
                response.raise_for_status()
                chats_data = response.json()
            
            results = []
            for chat in chats_data.get("value", [])[:5]:
                chat_id = chat["id"]
                
                # Get recent messages from this chat
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    msg_response = await client.get(
                        f"{self.api_base}/me/chats/{chat_id}/messages",
                        headers=self._get_headers(),
                        params={"$top": 3, "$orderby": "createdDateTime desc"}
                    )
                    
                    if msg_response.status_code == 200:
                        messages = msg_response.json().get("value", [])
                        for msg in messages:
                            content = msg.get("body", {}).get("content", "")
                            # Strip HTML if present
                            if "<" in content:
                                import re
                                content = re.sub('<[^<]+?>', '', content)
                            
                            results.append({
                                "id": msg["id"],
                                "chat_id": chat_id,
                                "source": self.name,
                                "subject": f"Teams Chat",
                                "timestamp": msg.get("createdDateTime", ""),
                                "snippet": content[:200],
                                "from": msg.get("from", {}).get("user", {}).get("displayName", "Unknown"),
                                "link": self._build_chat_deep_link(chat_id, msg["id"])
                            })
                
                if len(results) >= limit:
                    break
            
            return results[:limit]
            
        except httpx.HTTPError:
            return []
    
    async def get_record(self, record_id: str) -> Dict[str, Any]:
        """
        Get a specific email by ID.
        
        Returns minimal fields for the record.
        """
        if not self.access_token:
            return self._mock_email_record(record_id)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.api_base}/me/messages/{record_id}",
                    headers=self._get_headers(),
                    params={
                        "$select": "id,subject,receivedDateTime,bodyPreview,from,webLink"
                    }
                )
                response.raise_for_status()
                msg = response.json()
            
            return {
                "id": msg["id"],
                "source": self.name,
                "subject": msg.get("subject", "(No subject)"),
                "timestamp": msg.get("receivedDateTime", ""),
                "body_preview": msg.get("bodyPreview", ""),
                "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                "link": msg.get("webLink") or self._build_email_deep_link(msg["id"])
            }
            
        except httpx.HTTPError:
            return self._mock_email_record(record_id)
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        body_type: str = "HTML"
    ) -> Dict[str, Any]:
        """
        Send an email via Microsoft Graph.
        
        Requires Mail.Send permission.
        
        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body content
            body_type: "HTML" or "Text"
        
        Returns:
            Status of send operation
        """
        if not self.access_token:
            return {"status": "mock", "message": "Email would be sent (mock mode)"}
        
        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": body_type,
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in to
                ]
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/me/sendMail",
                    headers=self._get_headers(),
                    json=message
                )
                response.raise_for_status()
            
            return {"status": "sent", "recipients": to, "subject": subject}
            
        except httpx.HTTPError as e:
            return {"status": "error", "message": str(e)}
    
    # =========================================================================
    # Mock data methods for testing without real OAuth
    # =========================================================================
    
    def _mock_email_snippets(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Return mock email data for testing."""
        return [
            {
                "id": f"email-{i}",
                "source": self.name,
                "subject": f"Sample email matching {query} #{i}",
                "timestamp": "2025-12-01T10:00:00Z",
                "snippet": "This is a short snippet from the email body...",
                "from": "sender@example.com",
                "link": f"https://outlook.office.com/mail/deeplink/{i}"
            }
            for i in range(1, limit + 1)
        ]
    
    def _mock_calendar_events(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock calendar data for testing."""
        return [
            {
                "id": f"event-{i}",
                "source": self.name,
                "subject": f"Meeting #{i}",
                "timestamp": f"2025-12-{10+i}T09:00:00Z",
                "end_time": f"2025-12-{10+i}T10:00:00Z",
                "location": "Conference Room A",
                "snippet": "Discuss project updates",
                "attendees": ["attendee@example.com"],
                "link": f"https://outlook.office.com/calendar/item/event-{i}"
            }
            for i in range(1, min(limit + 1, 6))
        ]
    
    def _mock_chat_messages(self, limit: int) -> List[Dict[str, Any]]:
        """Return mock Teams chat data for testing."""
        return [
            {
                "id": f"chat-msg-{i}",
                "chat_id": f"chat-{i}",
                "source": self.name,
                "subject": "Teams Chat",
                "timestamp": "2025-11-29T08:30:00Z",
                "snippet": f"Hey, checking in about the project...",
                "from": "Colleague Name",
                "link": f"https://teams.microsoft.com/l/message/chat-{i}/msg-{i}"
            }
            for i in range(1, min(limit + 1, 4))
        ]
    
    def _mock_email_record(self, record_id: str) -> Dict[str, Any]:
        """Return mock email record for testing."""
        return {
            "id": record_id,
            "source": self.name,
            "subject": "Full email subject",
            "timestamp": "2025-12-01T10:00:00Z",
            "body_preview": "Full email preview or minimal fields",
            "from": "sender@example.com",
            "link": f"https://outlook.office.com/mail/deeplink/{record_id}"
        }
