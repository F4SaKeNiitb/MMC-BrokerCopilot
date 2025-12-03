"""
Salesforce OAuth 2.0 Implementation
Handles authorization code flow for Salesforce API access.
"""
import os
import time
import secrets
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import httpx

# Salesforce OAuth Configuration
SF_CLIENT_ID = os.getenv("SALESFORCE_CLIENT_ID", "")
SF_CLIENT_SECRET = os.getenv("SALESFORCE_CLIENT_SECRET", "")
SF_REDIRECT_URI = os.getenv("SALESFORCE_REDIRECT_URI", "http://localhost:8000/oauth/salesforce/callback")

# Salesforce OAuth endpoints (production)
SF_AUTH_URL = "https://login.salesforce.com/services/oauth2/authorize"
SF_TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
SF_REVOKE_URL = "https://login.salesforce.com/services/oauth2/revoke"

# For sandbox environments, use:
# SF_AUTH_URL = "https://test.salesforce.com/services/oauth2/authorize"
# SF_TOKEN_URL = "https://test.salesforce.com/services/oauth2/token"


@dataclass
class SalesforceTokenInfo:
    """Represents Salesforce OAuth tokens."""
    access_token: str
    instance_url: str
    token_type: str = "Bearer"
    refresh_token: Optional[str] = None
    issued_at: float = 0.0
    id_url: Optional[str] = None
    signature: Optional[str] = None
    
    def __post_init__(self):
        if self.issued_at == 0.0:
            self.issued_at = time.time()
    
    @property
    def is_expired(self) -> bool:
        """
        Salesforce tokens don't include expires_in, but typically last 2 hours.
        We'll consider them expired after 1.5 hours to be safe.
        """
        return time.time() >= (self.issued_at + 5400)  # 90 minutes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_url": self.instance_url,
            "token_type": self.token_type,
            "issued_at": self.issued_at,
            "is_expired": self.is_expired,
            "has_refresh_token": self.refresh_token is not None
        }


class SalesforceOAuthError(Exception):
    """Custom exception for Salesforce OAuth errors."""
    def __init__(self, error: str, description: str = "", status_code: int = 400):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")


class SalesforceOAuthClient:
    """
    Salesforce OAuth 2.0 client implementing authorization code flow.
    
    Supports:
    - Authorization URL generation
    - Token exchange
    - Token refresh
    - Token revocation
    """
    
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        redirect_uri: str = None,
        sandbox: bool = False
    ):
        self.client_id = client_id or SF_CLIENT_ID
        self.client_secret = client_secret or SF_CLIENT_SECRET
        self.redirect_uri = redirect_uri or SF_REDIRECT_URI
        
        # Use sandbox or production endpoints
        if sandbox:
            self.auth_url = "https://test.salesforce.com/services/oauth2/authorize"
            self.token_url = "https://test.salesforce.com/services/oauth2/token"
            self.revoke_url = "https://test.salesforce.com/services/oauth2/revoke"
        else:
            self.auth_url = SF_AUTH_URL
            self.token_url = SF_TOKEN_URL
            self.revoke_url = SF_REVOKE_URL
        
        # In-memory state store for CSRF protection
        self._pending_states: Dict[str, float] = {}
        
        # In-memory token store
        self._tokens: Dict[str, SalesforceTokenInfo] = {}
    
    def _validate_config(self):
        """Validate OAuth configuration."""
        if not self.client_id:
            raise SalesforceOAuthError("configuration_error", "SALESFORCE_CLIENT_ID not configured")
        if not self.client_secret:
            raise SalesforceOAuthError("configuration_error", "SALESFORCE_CLIENT_SECRET not configured")
    
    def generate_authorization_url(
        self,
        state: str = None,
        prompt: str = "login consent"
    ) -> Tuple[str, str]:
        """
        Generate Salesforce OAuth authorization URL.
        
        Args:
            state: Optional state parameter (generated if not provided)
            prompt: Prompt behavior (login, consent, or both)
        
        Returns:
            Tuple of (authorization_url, state)
        """
        self._validate_config()
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Store state with timestamp for validation
        self._pending_states[state] = time.time()
        
        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "prompt": prompt
        }
        
        from urllib.parse import urlencode
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        
        return auth_url, state
    
    async def exchange_code_for_tokens(
        self,
        code: str,
        state: str
    ) -> SalesforceTokenInfo:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
            state: State parameter for CSRF validation
        
        Returns:
            SalesforceTokenInfo with access token and instance URL
        """
        self._validate_config()
        
        # Validate state
        if state not in self._pending_states:
            raise SalesforceOAuthError(
                "invalid_state",
                "State parameter not found. Possible CSRF attack.",
                status_code=400
            )
        
        # Check state age (expire after 10 minutes)
        state_time = self._pending_states.pop(state)
        if time.time() - state_time > 600:
            raise SalesforceOAuthError(
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
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise SalesforceOAuthError(
                    error_data.get("error", "token_exchange_failed"),
                    error_data.get("error_description", "Failed to exchange code"),
                    status_code=response.status_code
                )
            
            token_data = response.json()
        
        token_info = SalesforceTokenInfo(
            access_token=token_data["access_token"],
            instance_url=token_data["instance_url"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=token_data.get("refresh_token"),
            issued_at=float(token_data.get("issued_at", time.time() * 1000)) / 1000,
            id_url=token_data.get("id"),
            signature=token_data.get("signature")
        )
        
        return token_info
    
    async def refresh_access_token(self, refresh_token: str) -> SalesforceTokenInfo:
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
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_data = response.json()
                raise SalesforceOAuthError(
                    error_data.get("error", "token_refresh_failed"),
                    error_data.get("error_description", "Failed to refresh token"),
                    status_code=response.status_code
                )
            
            token_data = response.json()
        
        # Refresh response may not include new refresh token
        return SalesforceTokenInfo(
            access_token=token_data["access_token"],
            instance_url=token_data["instance_url"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=refresh_token,  # Keep original refresh token
            issued_at=float(token_data.get("issued_at", time.time() * 1000)) / 1000
        )
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke an access or refresh token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.revoke_url,
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return response.status_code == 200
    
    async def get_user_info(self, token_info: SalesforceTokenInfo) -> Dict[str, Any]:
        """Get user info from the identity URL."""
        if not token_info.id_url:
            return {}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                token_info.id_url,
                headers={"Authorization": f"Bearer {token_info.access_token}"}
            )
            
            if response.status_code == 200:
                return response.json()
            return {}
    
    def store_user_token(self, user_id: str, token_info: SalesforceTokenInfo):
        """Store tokens for a user."""
        self._tokens[user_id] = token_info
    
    def get_user_token(self, user_id: str) -> Optional[SalesforceTokenInfo]:
        """Get stored token for a user."""
        return self._tokens.get(user_id)
    
    def remove_user_token(self, user_id: str):
        """Remove stored token."""
        self._tokens.pop(user_id, None)
    
    async def get_valid_token(self, user_id: str) -> Optional[SalesforceTokenInfo]:
        """Get a valid token, refreshing if needed."""
        token_info = self.get_user_token(user_id)
        
        if not token_info:
            return None
        
        if not token_info.is_expired:
            return token_info
        
        if not token_info.refresh_token:
            self.remove_user_token(user_id)
            return None
        
        try:
            new_token = await self.refresh_access_token(token_info.refresh_token)
            self.store_user_token(user_id, new_token)
            return new_token
        except SalesforceOAuthError:
            self.remove_user_token(user_id)
            return None


# Singleton instance
_sf_oauth_client: Optional[SalesforceOAuthClient] = None


def get_salesforce_oauth_client() -> SalesforceOAuthClient:
    """Get or create the Salesforce OAuth client singleton."""
    global _sf_oauth_client
    if _sf_oauth_client is None:
        _sf_oauth_client = SalesforceOAuthClient()
    return _sf_oauth_client
