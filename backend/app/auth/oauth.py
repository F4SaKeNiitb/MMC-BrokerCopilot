"""
OAuth 2.0 Implementation for Microsoft Graph API
Handles authorization code flow, token exchange, and refresh token lifecycle.
"""
import os
import time
import secrets
import hashlib
import base64
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlencode, quote
import httpx

from ..core.logging import get_logger, log_exception

logger = get_logger(__name__)

# Configuration from environment
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
AZURE_TENANT = os.getenv("AZURE_TENANT", "common")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/oauth/callback")

# Microsoft OAuth endpoints
AUTHORITY_URL = f"https://login.microsoftonline.com/{AZURE_TENANT}"
AUTHORIZE_ENDPOINT = f"{AUTHORITY_URL}/oauth2/v2.0/authorize"
TOKEN_ENDPOINT = f"{AUTHORITY_URL}/oauth2/v2.0/token"

# Default scopes for Broker Copilot
DEFAULT_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",  # Required for refresh tokens
    "User.Read",
    "Mail.Read",
    "Mail.Send",
    "Calendars.Read",
    "Chat.Read",
]


@dataclass
class TokenInfo:
    """Represents OAuth tokens with metadata."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    expires_at: float = 0.0
    refresh_token: Optional[str] = None
    scope: str = ""
    id_token: Optional[str] = None
    
    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = time.time() + self.expires_in
    
    @property
    def is_expired(self) -> bool:
        """Check if access token is expired (with 5 min buffer)."""
        return time.time() >= (self.expires_at - 300)
    
    @property
    def scopes_list(self) -> list:
        """Return scopes as a list."""
        return self.scope.split() if self.scope else []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive refresh token for logging)."""
        return {
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "is_expired": self.is_expired,
            "has_refresh_token": self.refresh_token is not None
        }


@dataclass
class PKCEChallenge:
    """PKCE (Proof Key for Code Exchange) challenge for enhanced security."""
    code_verifier: str = field(default_factory=lambda: secrets.token_urlsafe(64))
    
    @property
    def code_challenge(self) -> str:
        """Generate SHA256 code challenge from verifier."""
        digest = hashlib.sha256(self.code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    
    @property
    def code_challenge_method(self) -> str:
        return "S256"


class OAuthError(Exception):
    """Custom exception for OAuth-related errors."""
    def __init__(self, error: str, description: str = "", status_code: int = 400):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")


class MicrosoftOAuthClient:
    """
    Microsoft OAuth 2.0 client implementing authorization code flow with PKCE.
    
    This client handles:
    - Authorization URL generation with PKCE
    - Token exchange (auth code -> tokens)
    - Token refresh
    - Token validation
    
    SECURITY NOTES:
    - Tokens are stored in-memory only (ephemeral)
    - PKCE is used to prevent authorization code interception
    - State parameter prevents CSRF attacks
    - In production, consider using Azure Key Vault for client secrets
    """
    
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        tenant: str = None,
        redirect_uri: str = None
    ):
        self.client_id = client_id or AZURE_CLIENT_ID
        self.client_secret = client_secret or AZURE_CLIENT_SECRET
        self.tenant = tenant or AZURE_TENANT
        self.redirect_uri = redirect_uri or OAUTH_REDIRECT_URI
        
        # Update endpoints if tenant changed
        if self.tenant != AZURE_TENANT:
            self.authority_url = f"https://login.microsoftonline.com/{self.tenant}"
            self.authorize_endpoint = f"{self.authority_url}/oauth2/v2.0/authorize"
            self.token_endpoint = f"{self.authority_url}/oauth2/v2.0/token"
        else:
            self.authority_url = AUTHORITY_URL
            self.authorize_endpoint = AUTHORIZE_ENDPOINT
            self.token_endpoint = TOKEN_ENDPOINT
        
        # In-memory PKCE challenge store (keyed by state)
        # TODO: In production, use distributed cache (Redis) with TTL
        self._pkce_challenges: Dict[str, PKCEChallenge] = {}
        
        # In-memory token store (keyed by user_id)
        # TODO: In production, encrypt and store securely
        self._tokens: Dict[str, TokenInfo] = {}
    
    def _validate_config(self):
        """Validate OAuth configuration."""
        if not self.client_id:
            raise OAuthError("configuration_error", "AZURE_CLIENT_ID not configured")
        if not self.redirect_uri:
            raise OAuthError("configuration_error", "OAUTH_REDIRECT_URI not configured")
    
    def generate_authorization_url(
        self,
        scopes: list = None,
        state: str = None,
        login_hint: str = None,
        prompt: str = None
    ) -> Tuple[str, str, PKCEChallenge]:
        """
        Generate Microsoft OAuth authorization URL with PKCE.
        
        Args:
            scopes: List of permission scopes (defaults to DEFAULT_SCOPES)
            state: Optional state parameter (generated if not provided)
            login_hint: Optional email to pre-fill login
            prompt: Optional prompt behavior (login, consent, select_account, none)
        
        Returns:
            Tuple of (authorization_url, state, pkce_challenge)
        """
        self._validate_config()
        
        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Generate PKCE challenge
        pkce = PKCEChallenge()
        self._pkce_challenges[state] = pkce
        
        # Build scopes string
        scopes = scopes or DEFAULT_SCOPES
        scope_string = " ".join(scopes)
        
        # Build authorization URL parameters
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": scope_string,
            "state": state,
            "code_challenge": pkce.code_challenge,
            "code_challenge_method": pkce.code_challenge_method,
        }
        
        if login_hint:
            params["login_hint"] = login_hint
        
        if prompt:
            params["prompt"] = prompt
        
        auth_url = f"{self.authorize_endpoint}?{urlencode(params)}"
        
        return auth_url, state, pkce
    
    async def exchange_code_for_tokens(
        self,
        code: str,
        state: str
    ) -> TokenInfo:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
            state: State parameter to retrieve PKCE verifier
        
        Returns:
            TokenInfo with access_token, refresh_token, etc.
        
        Raises:
            OAuthError: If exchange fails
        """
        self._validate_config()
        
        # Retrieve PKCE challenge
        pkce = self._pkce_challenges.pop(state, None)
        if not pkce:
            raise OAuthError(
                "invalid_state",
                "State parameter not found or already used. Possible CSRF attack.",
                status_code=400
            )
        
        # Prepare token request
        data = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": pkce.code_verifier,
        }
        
        # Include client_secret for confidential clients
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        logger.info(f"Exchanging authorization code for tokens (state: {state[:8]}...)")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.token_endpoint,
                    data=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    logger.error(
                        f"Token exchange failed: {error_data.get('error')} - {error_data.get('error_description')}",
                        extra={"status_code": response.status_code}
                    )
                    raise OAuthError(
                        error_data.get("error", "token_exchange_failed"),
                        error_data.get("error_description", "Failed to exchange code for tokens"),
                        status_code=response.status_code
                    )
                
                token_data = response.json()
                logger.info("Token exchange successful")
                
        except httpx.TimeoutException:
            logger.error("Token exchange timed out")
            raise OAuthError("timeout", "Token exchange request timed out", status_code=504)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token exchange: {e}")
            raise OAuthError("http_error", f"HTTP error: {str(e)}", status_code=502)
        
        # Create TokenInfo
        token_info = TokenInfo(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token"),
            scope=token_data.get("scope", ""),
            id_token=token_data.get("id_token"),
        )
        
        return token_info
    
    async def refresh_access_token(
        self,
        refresh_token: str,
        scopes: list = None
    ) -> TokenInfo:
        """
        Refresh an expired access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            scopes: Optional scopes (defaults to original scopes)
        
        Returns:
            New TokenInfo with fresh access_token
        
        Raises:
            OAuthError: If refresh fails (e.g., refresh token expired)
        """
        self._validate_config()
        logger.debug("Attempting to refresh access token")
        
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        if scopes:
            data["scope"] = " ".join(scopes)
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.token_endpoint,
                    data=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    logger.warning(
                        f"Token refresh failed: {error_data.get('error')}",
                        extra={"status_code": response.status_code}
                    )
                    raise OAuthError(
                        error_data.get("error", "token_refresh_failed"),
                        error_data.get("error_description", "Failed to refresh token"),
                        status_code=response.status_code
                    )
                
                token_data = response.json()
                logger.info("Token refresh successful")
                
        except httpx.TimeoutException:
            logger.error("Token refresh timed out")
            raise OAuthError("timeout", "Token refresh request timed out", status_code=504)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token refresh: {e}")
            raise OAuthError("http_error", f"HTTP error: {str(e)}", status_code=502)
        
        token_info = TokenInfo(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token", refresh_token),  # May return new refresh token
            scope=token_data.get("scope", ""),
            id_token=token_data.get("id_token"),
        )
        
        return token_info
    
    def store_user_token(self, user_id: str, token_info: TokenInfo):
        """
        Store tokens for a user (in-memory, ephemeral).
        
        In production, tokens should be:
        - Encrypted at rest
        - Stored in secure vault or encrypted session
        - Associated with proper user identity
        """
        logger.debug(f"Storing token for user: {user_id}")
        self._tokens[user_id] = token_info
    
    def get_user_token(self, user_id: str) -> Optional[TokenInfo]:
        """Retrieve stored token for a user."""
        return self._tokens.get(user_id)
    
    def remove_user_token(self, user_id: str):
        """Remove stored token for a user (logout)."""
        logger.debug(f"Removing token for user: {user_id}")
        self._tokens.pop(user_id, None)
    
    async def get_valid_token(self, user_id: str) -> Optional[TokenInfo]:
        """
        Get a valid (non-expired) token for a user, refreshing if necessary.
        
        Args:
            user_id: User identifier
        
        Returns:
            Valid TokenInfo or None if no token/refresh failed
        """
        token_info = self.get_user_token(user_id)
        
        if not token_info:
            logger.debug(f"No token found for user: {user_id}")
            return None
        
        if not token_info.is_expired:
            logger.debug(f"Token for user {user_id} is still valid")
            return token_info
        
        logger.info(f"Token for user {user_id} is expired, attempting refresh")
        
        # Token is expired, try to refresh
        if not token_info.refresh_token:
            # No refresh token, user must re-authenticate
            logger.warning(f"No refresh token for user {user_id}, requiring re-authentication")
            self.remove_user_token(user_id)
            return None
        
        try:
            new_token = await self.refresh_access_token(token_info.refresh_token)
            self.store_user_token(user_id, new_token)
            logger.info(f"Token refreshed successfully for user {user_id}")
            return new_token
        except OAuthError as e:
            # Refresh failed, remove token
            logger.warning(f"Token refresh failed for user {user_id}: {e}")
            self.remove_user_token(user_id)
            return None
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch user profile information from Microsoft Graph.
        
        Args:
            access_token: Valid access token
        
        Returns:
            User profile dict with id, displayName, mail, etc.
        """
        logger.debug("Fetching user info from Microsoft Graph")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch user info: {response.status_code}")
                    raise OAuthError(
                        "user_info_failed",
                        f"Failed to fetch user info: {response.status_code}",
                        status_code=response.status_code
                    )
                
                user_info = response.json()
                logger.debug(f"User info retrieved for: {user_info.get('displayName', 'unknown')}")
                return user_info
                
        except httpx.TimeoutException:
            logger.error("User info request timed out")
            raise OAuthError("timeout", "User info request timed out", status_code=504)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching user info: {e}")
            raise OAuthError("http_error", f"HTTP error: {str(e)}", status_code=502)


# Singleton client instance
_oauth_client: Optional[MicrosoftOAuthClient] = None


def get_oauth_client() -> MicrosoftOAuthClient:
    """Get or create the OAuth client singleton."""
    global _oauth_client
    if _oauth_client is None:
        logger.debug("Creating Microsoft OAuth client singleton")
        _oauth_client = MicrosoftOAuthClient()
    return _oauth_client
