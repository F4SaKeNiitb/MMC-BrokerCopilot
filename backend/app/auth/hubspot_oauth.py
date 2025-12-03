"""
HubSpot OAuth 2.0 Implementation
Handles authorization code flow for HubSpot API access.
"""
import os
import time
import secrets
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import httpx

# HubSpot OAuth Configuration
HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID", "")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET", "")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/oauth/hubspot/callback")

# HubSpot OAuth endpoints
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_INFO_URL = "https://api.hubapi.com/oauth/v1/access-tokens"

# Default scopes for insurance broker functionality
DEFAULT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.companies.read",
    "crm.objects.companies.write",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
    "crm.schemas.contacts.read",
    "crm.schemas.companies.read",
    "crm.schemas.deals.read",
    "timeline"
]


@dataclass
class HubSpotTokenInfo:
    """Represents HubSpot OAuth tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 21600  # Default 6 hours
    acquired_at: float = 0.0
    hub_id: Optional[int] = None
    hub_domain: Optional[str] = None
    user: Optional[str] = None
    scopes: List[str] = None
    
    def __post_init__(self):
        if self.acquired_at == 0.0:
            self.acquired_at = time.time()
        if self.scopes is None:
            self.scopes = []
    
    @property
    def is_expired(self) -> bool:
        """Check if access token is expired (with 5 min buffer)."""
        return time.time() >= (self.acquired_at + self.expires_in - 300)
    
    @property
    def expires_at(self) -> float:
        """Get expiration timestamp."""
        return self.acquired_at + self.expires_in
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at,
            "is_expired": self.is_expired,
            "hub_id": self.hub_id,
            "hub_domain": self.hub_domain,
            "scopes": self.scopes
        }


class HubSpotOAuthError(Exception):
    """Custom exception for HubSpot OAuth errors."""
    def __init__(self, error: str, description: str = "", status_code: int = 400):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")


class HubSpotOAuthClient:
    """
    HubSpot OAuth 2.0 client implementing authorization code flow.
    
    Supports:
    - Authorization URL generation with scopes
    - Token exchange
    - Token refresh
    - Token info retrieval
    """
    
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        redirect_uri: str = None,
        scopes: List[str] = None
    ):
        self.client_id = client_id or HUBSPOT_CLIENT_ID
        self.client_secret = client_secret or HUBSPOT_CLIENT_SECRET
        self.redirect_uri = redirect_uri or HUBSPOT_REDIRECT_URI
        self.scopes = scopes or DEFAULT_SCOPES
        
        # In-memory state store for CSRF protection
        self._pending_states: Dict[str, float] = {}
        
        # In-memory token store
        self._tokens: Dict[str, HubSpotTokenInfo] = {}
    
    def _validate_config(self):
        """Validate OAuth configuration."""
        if not self.client_id:
            raise HubSpotOAuthError("configuration_error", "HUBSPOT_CLIENT_ID not configured")
        if not self.client_secret:
            raise HubSpotOAuthError("configuration_error", "HUBSPOT_CLIENT_SECRET not configured")
    
    def generate_authorization_url(
        self,
        state: str = None,
        scopes: List[str] = None,
        optional_scopes: List[str] = None
    ) -> Tuple[str, str]:
        """
        Generate HubSpot OAuth authorization URL.
        
        Args:
            state: Optional state parameter (generated if not provided)
            scopes: Required scopes (uses default if not provided)
            optional_scopes: Optional scopes user can grant
        
        Returns:
            Tuple of (authorization_url, state)
        """
        self._validate_config()
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Store state with timestamp for validation
        self._pending_states[state] = time.time()
        
        # Build authorization URL
        scope_list = scopes or self.scopes
        
        from urllib.parse import urlencode
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scope_list),
            "state": state
        }
        
        if optional_scopes:
            params["optional_scope"] = " ".join(optional_scopes)
        
        auth_url = f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"
        
        return auth_url, state
    
    async def exchange_code_for_tokens(
        self,
        code: str,
        state: str
    ) -> HubSpotTokenInfo:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
            state: State parameter for CSRF validation
        
        Returns:
            HubSpotTokenInfo with access and refresh tokens
        """
        self._validate_config()
        
        # Validate state
        if state not in self._pending_states:
            raise HubSpotOAuthError(
                "invalid_state",
                "State parameter not found. Possible CSRF attack.",
                status_code=400
            )
        
        # Check state age (expire after 10 minutes)
        state_time = self._pending_states.pop(state)
        if time.time() - state_time > 600:
            raise HubSpotOAuthError(
                "expired_state",
                "Authorization request expired. Please try again.",
                status_code=400
            )
        
        # Exchange code for tokens
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HUBSPOT_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise HubSpotOAuthError(
                    error_data.get("error", "token_exchange_failed"),
                    error_data.get("error_description", error_data.get("message", "Failed to exchange code")),
                    status_code=response.status_code
                )
            
            token_data = response.json()
        
        token_info = HubSpotTokenInfo(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 21600),
            acquired_at=time.time()
        )
        
        # Get token info for hub details
        info = await self.get_token_info(token_info.access_token)
        if info:
            token_info.hub_id = info.get("hub_id")
            token_info.hub_domain = info.get("hub_domain")
            token_info.user = info.get("user")
            token_info.scopes = info.get("scopes", [])
        
        return token_info
    
    async def refresh_access_token(self, refresh_token: str) -> HubSpotTokenInfo:
        """Refresh an expired access token."""
        self._validate_config()
        
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HUBSPOT_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise HubSpotOAuthError(
                    error_data.get("error", "token_refresh_failed"),
                    error_data.get("error_description", error_data.get("message", "Failed to refresh token")),
                    status_code=response.status_code
                )
            
            token_data = response.json()
        
        token_info = HubSpotTokenInfo(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 21600),
            acquired_at=time.time()
        )
        
        # Get updated token info
        info = await self.get_token_info(token_info.access_token)
        if info:
            token_info.hub_id = info.get("hub_id")
            token_info.hub_domain = info.get("hub_domain")
            token_info.user = info.get("user")
            token_info.scopes = info.get("scopes", [])
        
        return token_info
    
    async def get_token_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get information about an access token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{HUBSPOT_INFO_URL}/{access_token}"
            )
            
            if response.status_code == 200:
                return response.json()
            return None
    
    def store_user_token(self, user_id: str, token_info: HubSpotTokenInfo):
        """Store tokens for a user."""
        self._tokens[user_id] = token_info
    
    def get_user_token(self, user_id: str) -> Optional[HubSpotTokenInfo]:
        """Get stored token for a user."""
        return self._tokens.get(user_id)
    
    def remove_user_token(self, user_id: str):
        """Remove stored token."""
        self._tokens.pop(user_id, None)
    
    async def get_valid_token(self, user_id: str) -> Optional[HubSpotTokenInfo]:
        """Get a valid token, refreshing if needed."""
        token_info = self.get_user_token(user_id)
        
        if not token_info:
            return None
        
        if not token_info.is_expired:
            return token_info
        
        try:
            new_token = await self.refresh_access_token(token_info.refresh_token)
            self.store_user_token(user_id, new_token)
            return new_token
        except HubSpotOAuthError:
            self.remove_user_token(user_id)
            return None


# Singleton instance
_hubspot_oauth_client: Optional[HubSpotOAuthClient] = None


def get_hubspot_oauth_client() -> HubSpotOAuthClient:
    """Get or create the HubSpot OAuth client singleton."""
    global _hubspot_oauth_client
    if _hubspot_oauth_client is None:
        _hubspot_oauth_client = HubSpotOAuthClient()
    return _hubspot_oauth_client
