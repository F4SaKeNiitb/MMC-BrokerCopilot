import os
import time
import traceback
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Query, Depends
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError as PydanticValidationError
from dotenv import load_dotenv
import asyncio
from typing import Dict, Any, List, Optional

from .core.logging import get_logger, configure_logging, LogContext
from .core.exceptions import (
    BrokerCopilotError,
    ConfigurationError,
    AuthenticationError,
    ValidationError,
    ExternalServiceError,
    ConnectorError,
    LLMError,
    PDFGenerationError,
    NotFoundError,
)
from .core.middleware import RequestContextMiddleware
from .connectors.microsoft_graph import MicrosoftGraphConnector
from .connectors.salesforce import SalesforceConnector
from .connectors.hubspot import HubSpotConnector
from .brief import generate_brief, stream_brief
from .chat_agent import handle_chat_message, stream_chat_response
from .priority import deterministic_score
from .templates import render_template
from .pdf_generator import generate_brief_pdf, create_sample_brief_content
from .auth.oauth import get_oauth_client, OAuthError, TokenInfo
from .auth.salesforce_oauth import get_salesforce_oauth_client, SalesforceOAuthError, SalesforceTokenInfo
from .auth.hubspot_oauth import get_hubspot_oauth_client, HubSpotOAuthError, HubSpotTokenInfo
from .email.router import router as email_router

# Initialize logging
load_dotenv()
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("LOG_FORMAT", "text").lower() == "json",
)
logger = get_logger(__name__)

app = FastAPI(
    title="Broker Copilot - Backend",
    description="AI-augmented workflow platform for insurance brokers. Zero-storage, connector-driven architecture.",
    version="1.0.0"
)

# =============================================================================
# Middleware Configuration
# =============================================================================

# Request context middleware (adds request ID, timing, logging)
app.add_middleware(RequestContextMiddleware)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Global Exception Handlers
# =============================================================================

@app.exception_handler(BrokerCopilotError)
async def broker_copilot_exception_handler(request: Request, exc: BrokerCopilotError):
    """Handle all Broker Copilot domain exceptions."""
    logger.error(
        f"Domain error: {exc.error_code.value} - {exc.message}",
        extra={
            "error_code": exc.error_code.value,
            "http_status": exc.http_status,
            "context": exc.context,
            "path": request.url.path,
        }
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors from request parsing."""
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error["loc"])
        errors.append({
            "field": loc,
            "message": error["msg"],
            "type": error["type"],
        })
    
    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={"errors": errors}
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "error_code": "ERR_1003",
            "message": "Request validation failed",
            "detail": errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTPExceptions."""
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Handle any unhandled exceptions - last resort."""
    # Log the full traceback
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
    )
    
    # Don't expose internal errors in production
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "error_code": "ERR_1001",
            "message": "An internal server error occurred",
            "detail": str(exc) if is_debug else "Please contact support if this persists",
        },
    )


# Include email scheduling router
app.include_router(email_router)

logger.info("Broker Copilot backend initialized successfully")

# In-memory ephemeral token store (per process only). Do NOT use in prod.
# TODO: Replace with secure, per-user token vault or integrate with broker's SSO.
EPHEMERAL_TOKENS: Dict[str, Dict[str, Any]] = {}


class AggregateQuery(BaseModel):
    query: str
    limit: int = 5


@app.get("/health")
async def health():
    """Health check endpoint for monitoring and load balancer probes."""
    return {
        "status": "ok",
        "service": "broker-copilot",
        "version": "1.0.0",
        "timestamp": time.time(),
    }


@app.post("/aggregate")
async def aggregate(q: AggregateQuery):
    """
    Aggregate snippets from multiple connectors in parallel.
    Returns source-level results plus which sources failed.
    """
    logger.info(f"Aggregate request for query: {q.query[:50]}...")
    
    results = {}
    failures = []

    # For now we only have MicrosoftGraphConnector in scaffold
    mg = MicrosoftGraphConnector({})

    async def safe_fetch(name: str, coro):
        """Safely fetch from a connector with error handling."""
        try:
            res = await coro
            results[name] = res
            logger.debug(f"Connector {name} returned {len(res)} results")
        except asyncio.TimeoutError:
            logger.warning(f"Connector {name} timed out")
            failures.append({"source": name, "error": "Connection timed out"})
        except ConnectorError as e:
            logger.warning(f"Connector {name} error: {e}")
            failures.append({"source": name, "error": str(e)})
        except Exception as e:
            logger.error(f"Unexpected error from connector {name}: {e}", exc_info=True)
            failures.append({"source": name, "error": f"Unexpected error: {type(e).__name__}"})

    try:
        # Kick off concurrent fetches with timeout
        tasks = [safe_fetch(mg.name, mg.fetch_snippets(query=q.query, limit=q.limit))]
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Aggregate request timed out globally")
        failures.append({"source": "aggregate", "error": "Global timeout exceeded"})

    logger.info(f"Aggregate completed: {len(results)} sources, {len(failures)} failures")
    return {"results": results, "failures": failures}


@app.get("/score/{policy_id}")
async def score_policy(policy_id: str):
    """Calculate deterministic priority score for a policy renewal."""
    logger.debug(f"Calculating score for policy: {policy_id}")
    
    try:
        # Mock policy fetch - in production this calls CRM connector
        policy = {
            "id": policy_id, 
            "premium_at_risk": 125000.0, 
            "days_to_expiry": 43, 
            "claims_frequency": 1
        }
        
        score, breakdown = deterministic_score(policy)
        
        # Generate human-readable explanation
        if score >= 0.8:
            interpretation = "CRITICAL - Immediate action required"
        elif score >= 0.6:
            interpretation = "HIGH - Prioritize this week"
        elif score >= 0.4:
            interpretation = "MEDIUM - Schedule follow-up"
        else:
            interpretation = "LOW - Monitor and plan"
        
        logger.debug(f"Score for {policy_id}: {score:.2f} ({interpretation})")
        
        return {
            "policy": policy, 
            "score": score, 
            "breakdown": breakdown,
            "interpretation": interpretation
        }
        
    except Exception as e:
        logger.error(f"Error calculating score for policy {policy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Score calculation failed: {str(e)}")


@app.get("/brief/{policy_id}")
async def brief(policy_id: str, stream: bool = Query(default=True)):
    """
    Generate a comprehensive one-page brief for a policy renewal.
    
    - Fetches data from multiple sources (CRM, Email, Calendar, Teams) concurrently
    - Uses Gemini LLM to synthesize insights with citations
    - Returns streaming response by default for reduced perceived latency
    
    Query params:
    - stream: If true (default), streams the response. If false, returns JSON.
    """
    logger.info(f"Generating brief for policy: {policy_id} (stream={stream})")
    
    try:
        if stream:
            return StreamingResponse(
                stream_brief(policy_id, connectors_settings={}),
                media_type="text/plain"
            )
        else:
            # Non-streaming JSON response
            data = await generate_brief(policy_id, connectors_settings={})
            logger.debug(f"Brief generated successfully for {policy_id}")
            return JSONResponse(data)
    except LLMError as e:
        logger.error(f"LLM error generating brief for {policy_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Brief generation failed: {str(e)}")
    except ConnectorError as e:
        logger.error(f"Connector error generating brief for {policy_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error generating brief for {policy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Brief generation failed: {str(e)}")


@app.get("/brief/{policy_id}/pdf")
async def brief_pdf(policy_id: str):
    """
    Generate a PDF version of the one-page brief.
    
    - Fetches brief content (non-streaming)
    - Converts to professional PDF with styling
    - Returns PDF file for download
    
    Returns:
        PDF file with Content-Disposition header for download
    """
    logger.info(f"Generating PDF brief for policy: {policy_id}")
    
    # Get policy data for context
    policy = {
        "id": policy_id,
        "policy_number": policy_id,
        "client_name": "ACME Corporation",
        "premium_at_risk": 125000.0,
        "expiry_date": "2026-01-15",
        "days_to_expiry": 43,
        "claims_frequency": 1,
        "policy_type": "Commercial Property",
    }
    
    # Calculate score
    try:
        score, _ = deterministic_score(policy)
    except Exception as e:
        logger.warning(f"Score calculation failed for {policy_id}, using default: {e}")
        score = 0.5
    
    # Get brief content
    content = None
    try:
        # Try to get actual brief content
        brief_data = await generate_brief(policy_id, connectors_settings={})
        content = brief_data.get("brief", "") if isinstance(brief_data, dict) else str(brief_data)
        
        # If content is empty or too short, use sample
        if not content or len(content) < 100:
            logger.debug(f"Brief content too short for {policy_id}, using sample")
            content = create_sample_brief_content(policy_id, policy)
    except Exception as e:
        logger.warning(f"Brief generation failed for {policy_id}, using sample: {e}")
        # Fallback to sample content
        content = create_sample_brief_content(policy_id, policy)
    
    # Generate PDF
    try:
        pdf_bytes = generate_brief_pdf(
            policy_id=policy_id,
            content=content,
            policy_data=policy,
            score=score
        )
        logger.info(f"PDF generated successfully for {policy_id}, size: {len(pdf_bytes)} bytes")
    except PDFGenerationError as e:
        logger.error(f"PDF generation failed for {policy_id}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error generating PDF for {policy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    
    # Return PDF response
    filename = f"brief_{policy_id}_{int(time.time())}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        }
    )


class ChatPayload(BaseModel):
    user_id: str
    message: str
    stream: bool = False


@app.post("/chat")
async def chat(payload: ChatPayload):
    """
    Connector-backed Q&A chat endpoint with function-calling support.
    
    - Uses Gemini with function-calling for multi-hop reasoning
    - Can chain multiple data lookups to answer complex questions
    - Returns confidence score and provenance links for transparency
    - Includes hallucination guardrails - refuses to guess if data not found
    
    Example queries:
    - "Who is the underwriter for POL-123 and when did I last email them?"
    - "What's the priority score for POL-456?"
    - "Find emails about the Smith account renewal"
    """
    logger.info(f"Chat request from user {payload.user_id}: {payload.message[:50]}...")
    
    try:
        if payload.stream:
            return StreamingResponse(
                stream_chat_response(payload.dict(), connectors_settings={}),
                media_type="text/plain"
            )
        else:
            res = await handle_chat_message(payload.dict(), connectors_settings={})
            logger.debug(f"Chat response generated for user {payload.user_id}")
            return JSONResponse(res)
    except LLMError as e:
        logger.error(f"LLM error in chat for user {payload.user_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Chat processing failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in chat for user {payload.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@app.post("/chat/stream")
async def chat_stream(payload: ChatPayload):
    """Streaming chat endpoint - always streams response."""
    logger.info(f"Streaming chat request from user {payload.user_id}")
    
    try:
        return StreamingResponse(
            stream_chat_response(payload.dict(), connectors_settings={}),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error in streaming chat for user {payload.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat streaming failed: {str(e)}")


class TemplatePayload(BaseModel):
    template: str
    context: Dict[str, Any]


@app.post("/render-template")
async def render_template_endpoint(payload: TemplatePayload):
    """
    Render a Jinja2 template with dynamic context from live data.
    
    - Supports Markdown + Jinja2 syntax
    - Returns both Markdown and HTML versions
    - Use for email templates, reports, etc.
    """
    logger.debug("Rendering template")
    
    try:
        rendered = render_template(payload.template, payload.context)
        # Return rendered markdown plus a simple HTML conversion
        import markdown
        html = markdown.markdown(rendered)
        return {"markdown": rendered, "html": html}
    except Exception as e:
        logger.error(f"Template rendering failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Template rendering failed: {str(e)}")


class RenewalFilter(BaseModel):
    days_window: int = 90  # 30, 60, 90 days
    policy_type: Optional[str] = None
    assignee: Optional[str] = None
    sort_by: str = "score"  # score, expiry, premium


@app.post("/renewals")
async def get_renewals(filters: RenewalFilter):
    """
    Get upcoming policy renewals with live prioritization.
    
    - Fetches renewal data from CRM connector
    - Applies deterministic scoring with LLM explanation
    - Supports filtering by time window, policy type, assignee
    - Returns pipeline data suitable for Kanban/list visualization
    """
    logger.info(f"Fetching renewals with filters: {filters.dict()}")
    
    # TODO: Replace with actual CRM connector call
    # Mock renewals data
    renewals = [
        {
            "id": "POL-123",
            "policy_number": "POL-123",
            "client_name": "ACME Corporation",
            "premium_at_risk": 125000.0,
            "expiry_date": "2026-01-15",
            "days_to_expiry": 43,
            "claims_frequency": 1,
            "policy_type": "Commercial Property",
            "assignee": "john.broker@company.com",
            "link": "https://crm.example.com/policy/POL-123"
        },
        {
            "id": "POL-456",
            "policy_number": "POL-456",
            "client_name": "Smith Industries",
            "premium_at_risk": 75000.0,
            "expiry_date": "2026-01-30",
            "days_to_expiry": 58,
            "claims_frequency": 3,
            "policy_type": "General Liability",
            "assignee": "jane.broker@company.com",
            "link": "https://crm.example.com/policy/POL-456"
        },
        {
            "id": "POL-789",
            "policy_number": "POL-789",
            "client_name": "TechStart Inc",
            "premium_at_risk": 250000.0,
            "expiry_date": "2026-02-28",
            "days_to_expiry": 87,
            "claims_frequency": 0,
            "policy_type": "Cyber Liability",
            "assignee": "john.broker@company.com",
            "link": "https://crm.example.com/policy/POL-789"
        }
    ]
    
    # Apply filters
    filtered = []
    for r in renewals:
        if r["days_to_expiry"] > filters.days_window:
            continue
        if filters.policy_type and r["policy_type"] != filters.policy_type:
            continue
        if filters.assignee and r["assignee"] != filters.assignee:
            continue
        
        # Calculate score
        score, breakdown = deterministic_score(r)
        r["score"] = score
        r["score_breakdown"] = breakdown
        
        # Generate LLM explanation (simplified for non-LLM mode)
        if score >= 0.7:
            r["priority_explanation"] = f"High priority due to ${r['premium_at_risk']:,.0f} premium with {r['days_to_expiry']} days to expiry."
        elif score >= 0.5:
            r["priority_explanation"] = f"Medium priority - {r['days_to_expiry']} days until expiry, monitor closely."
        else:
            r["priority_explanation"] = f"Lower priority - sufficient time remaining ({r['days_to_expiry']} days)."
        
        filtered.append(r)
    
    # Sort
    if filters.sort_by == "score":
        filtered.sort(key=lambda x: x["score"], reverse=True)
    elif filters.sort_by == "expiry":
        filtered.sort(key=lambda x: x["days_to_expiry"])
    elif filters.sort_by == "premium":
        filtered.sort(key=lambda x: x["premium_at_risk"], reverse=True)
    
    return {
        "renewals": filtered,
        "total": len(filtered),
        "filters_applied": filters.dict()
    }


class OverridePayload(BaseModel):
    policy_id: str
    override_score: float
    reason: str


@app.post("/renewals/override")
async def override_priority(payload: OverridePayload):
    """
    Allow manual override of AI priority score.
    
    Since we have no persistent DB, this either:
    - Writes to a CRM custom field (if permitted)
    - Returns instruction to store in user preferences
    
    # TODO: Implement CRM write-back when connector supports it
    """
    return {
        "status": "accepted",
        "policy_id": payload.policy_id,
        "override_score": payload.override_score,
        "reason": payload.reason,
        "note": "Override recorded. In production, this would write to CRM custom field or user preferences."
    }


# =============================================================================
# OAuth 2.0 Endpoints - Microsoft Graph Authentication
# =============================================================================

class OAuthStartRequest(BaseModel):
    """Request to start OAuth flow."""
    provider: str = "microsoft"
    login_hint: Optional[str] = None  # Pre-fill email if known
    scopes: Optional[List[str]] = None  # Custom scopes (uses defaults if not provided)


class OAuthStartResponse(BaseModel):
    """Response with authorization URL."""
    auth_url: str
    state: str
    provider: str


@app.post("/oauth/start", response_model=OAuthStartResponse)
async def oauth_start(request: OAuthStartRequest):
    """
    Start OAuth 2.0 authorization flow.
    
    Returns an authorization URL that the frontend should redirect the user to.
    Uses PKCE (Proof Key for Code Exchange) for enhanced security.
    
    Flow:
    1. Frontend calls this endpoint
    2. Redirect user to returned auth_url
    3. User authenticates with Microsoft
    4. Microsoft redirects to /oauth/callback with code
    5. Backend exchanges code for tokens
    """
    if request.provider != "microsoft":
        raise HTTPException(status_code=400, detail="Only 'microsoft' provider is supported")
    
    oauth_client = get_oauth_client()
    
    try:
        auth_url, state, pkce = oauth_client.generate_authorization_url(
            scopes=request.scopes,
            login_hint=request.login_hint,
            prompt="select_account"  # Allow user to choose account
        )
        
        return OAuthStartResponse(
            auth_url=auth_url,
            state=state,
            provider=request.provider
        )
    except OAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


@app.get("/oauth/callback")
async def oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """
    OAuth 2.0 callback endpoint.
    
    Microsoft redirects here after user authentication.
    Exchanges authorization code for tokens using PKCE.
    
    Query Parameters:
    - code: Authorization code (on success)
    - state: State parameter for CSRF protection and PKCE lookup
    - error: Error code (on failure)
    - error_description: Human-readable error description
    
    Returns:
    - On success: User info and token metadata (not the token itself)
    - On failure: Error details
    
    The frontend should handle the redirect and call this endpoint,
    or this endpoint can redirect to a frontend success/error page.
    """
    # Handle OAuth errors
    if error:
        # In production, redirect to frontend error page
        raise HTTPException(
            status_code=400,
            detail={
                "error": error,
                "description": error_description or "OAuth authentication failed"
            }
        )
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")
    
    oauth_client = get_oauth_client()
    
    try:
        # Exchange code for tokens
        token_info = await oauth_client.exchange_code_for_tokens(code, state)
        
        # Get user info to identify the user
        user_info = await oauth_client.get_user_info(token_info.access_token)
        
        # Use Microsoft's user ID as our user identifier
        user_id = user_info.get("id", state)
        
        # Store token for this user (in-memory, ephemeral)
        oauth_client.store_user_token(user_id, token_info)
        
        # Return success response
        # In production, you might redirect to frontend with a session cookie
        return {
            "status": "authenticated",
            "user": {
                "id": user_id,
                "display_name": user_info.get("displayName"),
                "email": user_info.get("mail") or user_info.get("userPrincipalName"),
                "job_title": user_info.get("jobTitle"),
            },
            "token_info": token_info.to_dict(),
            "message": "Successfully authenticated. Token stored for this session."
        }
        
    except OAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


@app.get("/oauth/refresh")
async def oauth_refresh(user_id: str):
    """
    Manually refresh an access token.
    
    Normally tokens are auto-refreshed when needed, but this endpoint
    allows explicit refresh for testing or proactive token renewal.
    """
    oauth_client = get_oauth_client()
    
    token_info = oauth_client.get_user_token(user_id)
    if not token_info:
        raise HTTPException(status_code=401, detail="No token found for user. Please authenticate first.")
    
    if not token_info.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available. User must re-authenticate.")
    
    try:
        new_token = await oauth_client.refresh_access_token(token_info.refresh_token)
        oauth_client.store_user_token(user_id, new_token)
        
        return {
            "status": "refreshed",
            "user_id": user_id,
            "token_info": new_token.to_dict()
        }
    except OAuthError as e:
        oauth_client.remove_user_token(user_id)
        raise HTTPException(status_code=e.status_code, detail=f"Token refresh failed: {e.description}")


@app.get("/oauth/status")
async def oauth_status(user_id: str):
    """
    Check authentication status for a user.
    
    Returns token status without exposing the actual token.
    """
    oauth_client = get_oauth_client()
    
    token_info = oauth_client.get_user_token(user_id)
    if not token_info:
        return {
            "authenticated": False,
            "user_id": user_id,
            "message": "No active session. Please authenticate."
        }
    
    return {
        "authenticated": True,
        "user_id": user_id,
        "token_info": token_info.to_dict(),
        "needs_refresh": token_info.is_expired
    }


@app.post("/oauth/logout")
async def oauth_logout(user_id: str):
    """
    Log out a user by removing their stored tokens.
    
    Note: This only removes tokens from our store.
    For complete logout, redirect user to Microsoft's logout endpoint:
    https://login.microsoftonline.com/common/oauth2/v2.0/logout
    """
    oauth_client = get_oauth_client()
    oauth_client.remove_user_token(user_id)
    
    # Microsoft logout URL for complete sign-out
    ms_logout_url = "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
    
    return {
        "status": "logged_out",
        "user_id": user_id,
        "microsoft_logout_url": ms_logout_url,
        "message": "Token removed. Redirect to microsoft_logout_url for complete sign-out."
    }


@app.get("/oauth/me")
async def oauth_me(user_id: str):
    """
    Get current user's profile from Microsoft Graph.
    
    Requires valid authentication. Auto-refreshes token if needed.
    """
    oauth_client = get_oauth_client()
    
    token_info = await oauth_client.get_valid_token(user_id)
    if not token_info:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated or session expired. Please authenticate again."
        )
    
    try:
        user_info = await oauth_client.get_user_info(token_info.access_token)
        return {
            "user": user_info,
            "token_status": token_info.to_dict()
        }
    except OAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


# Helper dependency for protected endpoints
async def get_current_user_token(user_id: str) -> TokenInfo:
    """
    Dependency to get valid token for current user.
    Use this to protect endpoints that require authentication.
    """
    oauth_client = get_oauth_client()
    token_info = await oauth_client.get_valid_token(user_id)
    
    if not token_info:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please authenticate via /oauth/start"
        )
    
    return token_info


# =============================================================================
# Salesforce OAuth 2.0 Endpoints
# =============================================================================

@app.post("/oauth/salesforce/start")
async def salesforce_oauth_start():
    """
    Start Salesforce OAuth 2.0 authorization flow.
    
    Returns an authorization URL that the frontend should redirect the user to.
    """
    sf_oauth = get_salesforce_oauth_client()
    
    try:
        auth_url, state = sf_oauth.generate_authorization_url()
        
        return {
            "auth_url": auth_url,
            "state": state,
            "provider": "salesforce"
        }
    except SalesforceOAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


@app.get("/oauth/salesforce/callback")
async def salesforce_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """
    Salesforce OAuth 2.0 callback endpoint.
    
    Exchanges authorization code for tokens.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail={"error": error, "description": error_description or "Salesforce OAuth failed"}
        )
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")
    
    sf_oauth = get_salesforce_oauth_client()
    
    try:
        token_info = await sf_oauth.exchange_code_for_tokens(code, state)
        
        # Get user info
        user_info = await sf_oauth.get_user_info(token_info)
        user_id = user_info.get("user_id", state)
        
        # Store token
        sf_oauth.store_user_token(user_id, token_info)
        
        return {
            "status": "authenticated",
            "provider": "salesforce",
            "user": {
                "id": user_id,
                "display_name": user_info.get("display_name"),
                "email": user_info.get("email"),
                "organization_id": user_info.get("organization_id")
            },
            "instance_url": token_info.instance_url,
            "token_info": token_info.to_dict()
        }
    except SalesforceOAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


@app.get("/oauth/salesforce/status")
async def salesforce_oauth_status(user_id: str):
    """Check Salesforce authentication status for a user."""
    sf_oauth = get_salesforce_oauth_client()
    token_info = sf_oauth.get_user_token(user_id)
    
    if not token_info:
        return {"authenticated": False, "provider": "salesforce", "user_id": user_id}
    
    return {
        "authenticated": True,
        "provider": "salesforce",
        "user_id": user_id,
        "token_info": token_info.to_dict(),
        "needs_refresh": token_info.is_expired
    }


@app.post("/oauth/salesforce/logout")
async def salesforce_oauth_logout(user_id: str):
    """Log out from Salesforce by removing stored tokens."""
    sf_oauth = get_salesforce_oauth_client()
    token_info = sf_oauth.get_user_token(user_id)
    
    if token_info:
        await sf_oauth.revoke_token(token_info.access_token)
        sf_oauth.remove_user_token(user_id)
    
    return {"status": "logged_out", "provider": "salesforce", "user_id": user_id}


# =============================================================================
# HubSpot OAuth 2.0 Endpoints
# =============================================================================

@app.post("/oauth/hubspot/start")
async def hubspot_oauth_start(scopes: Optional[List[str]] = None):
    """
    Start HubSpot OAuth 2.0 authorization flow.
    
    Returns an authorization URL that the frontend should redirect the user to.
    """
    hs_oauth = get_hubspot_oauth_client()
    
    try:
        auth_url, state = hs_oauth.generate_authorization_url(scopes=scopes)
        
        return {
            "auth_url": auth_url,
            "state": state,
            "provider": "hubspot"
        }
    except HubSpotOAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


@app.get("/oauth/hubspot/callback")
async def hubspot_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """
    HubSpot OAuth 2.0 callback endpoint.
    
    Exchanges authorization code for tokens.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail={"error": error, "description": error_description or "HubSpot OAuth failed"}
        )
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")
    
    hs_oauth = get_hubspot_oauth_client()
    
    try:
        token_info = await hs_oauth.exchange_code_for_tokens(code, state)
        
        # Use hub_id as user identifier
        user_id = str(token_info.hub_id) if token_info.hub_id else state
        
        # Store token
        hs_oauth.store_user_token(user_id, token_info)
        
        return {
            "status": "authenticated",
            "provider": "hubspot",
            "user": {
                "id": user_id,
                "hub_id": token_info.hub_id,
                "hub_domain": token_info.hub_domain,
                "user": token_info.user
            },
            "scopes": token_info.scopes,
            "token_info": token_info.to_dict()
        }
    except HubSpotOAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.description)


@app.get("/oauth/hubspot/status")
async def hubspot_oauth_status(user_id: str):
    """Check HubSpot authentication status for a user."""
    hs_oauth = get_hubspot_oauth_client()
    token_info = hs_oauth.get_user_token(user_id)
    
    if not token_info:
        return {"authenticated": False, "provider": "hubspot", "user_id": user_id}
    
    return {
        "authenticated": True,
        "provider": "hubspot",
        "user_id": user_id,
        "token_info": token_info.to_dict(),
        "needs_refresh": token_info.is_expired
    }


@app.post("/oauth/hubspot/logout")
async def hubspot_oauth_logout(user_id: str):
    """Log out from HubSpot by removing stored tokens."""
    hs_oauth = get_hubspot_oauth_client()
    hs_oauth.remove_user_token(user_id)
    
    return {"status": "logged_out", "provider": "hubspot", "user_id": user_id}


# =============================================================================
# CRM Data Endpoints - Unified Interface for Salesforce/HubSpot
# =============================================================================

class CRMQuery(BaseModel):
    """Query parameters for CRM data fetching."""
    provider: str  # "salesforce" or "hubspot"
    user_id: str


@app.post("/crm/renewals")
async def get_crm_renewals(query: CRMQuery, days_window: int = 90):
    """
    Get upcoming policy renewals from CRM system.
    
    Fetches renewal pipeline from either Salesforce or HubSpot
    based on user's connected CRM system.
    """
    if query.provider == "salesforce":
        sf_oauth = get_salesforce_oauth_client()
        token_info = await sf_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="Salesforce authentication required")
        
        connector = SalesforceConnector(token_info.access_token, token_info.instance_url)
        renewals = await connector.get_renewal_pipeline(days=days_window)
        
    elif query.provider == "hubspot":
        hs_oauth = get_hubspot_oauth_client()
        token_info = await hs_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="HubSpot authentication required")
        
        connector = HubSpotConnector(token_info.access_token)
        renewals = await connector.get_renewal_pipeline(days=days_window)
        
    else:
        raise HTTPException(status_code=400, detail="Invalid CRM provider")
    
    # Apply priority scoring to each renewal
    for renewal in renewals:
        score, breakdown = deterministic_score(renewal)
        renewal["score"] = score
        renewal["score_breakdown"] = breakdown
        
        if score >= 0.7:
            renewal["priority_explanation"] = f"High priority - requires immediate attention"
        elif score >= 0.5:
            renewal["priority_explanation"] = f"Medium priority - monitor closely"
        else:
            renewal["priority_explanation"] = f"Lower priority - sufficient time remaining"
    
    # Sort by score
    renewals.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return {
        "renewals": renewals,
        "total": len(renewals),
        "provider": query.provider,
        "days_window": days_window
    }


@app.post("/crm/policy/{policy_id}")
async def get_crm_policy(policy_id: str, query: CRMQuery):
    """Get detailed policy information from CRM."""
    if query.provider == "salesforce":
        sf_oauth = get_salesforce_oauth_client()
        token_info = await sf_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="Salesforce authentication required")
        
        connector = SalesforceConnector(token_info.access_token, token_info.instance_url)
        policy = await connector.get_policy(policy_id)
        
    elif query.provider == "hubspot":
        hs_oauth = get_hubspot_oauth_client()
        token_info = await hs_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="HubSpot authentication required")
        
        connector = HubSpotConnector(token_info.access_token)
        policy = await connector.get_deal(policy_id)  # Policies are deals in HubSpot
        
    else:
        raise HTTPException(status_code=400, detail="Invalid CRM provider")
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return {"policy": policy, "provider": query.provider}


@app.post("/crm/client/{client_id}")
async def get_crm_client(client_id: str, query: CRMQuery):
    """Get client/account information from CRM."""
    if query.provider == "salesforce":
        sf_oauth = get_salesforce_oauth_client()
        token_info = await sf_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="Salesforce authentication required")
        
        connector = SalesforceConnector(token_info.access_token, token_info.instance_url)
        client = await connector.get_client(client_id)
        
    elif query.provider == "hubspot":
        hs_oauth = get_hubspot_oauth_client()
        token_info = await hs_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="HubSpot authentication required")
        
        connector = HubSpotConnector(token_info.access_token)
        client = await connector.get_company(client_id)
        
    else:
        raise HTTPException(status_code=400, detail="Invalid CRM provider")
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return {"client": client, "provider": query.provider}


@app.post("/crm/search")
async def search_crm(query: CRMQuery, search_term: str, entity_type: str = "policies"):
    """
    Search CRM for policies, clients, or contacts.
    
    entity_type: "policies", "clients", "contacts"
    """
    if query.provider == "salesforce":
        sf_oauth = get_salesforce_oauth_client()
        token_info = await sf_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="Salesforce authentication required")
        
        connector = SalesforceConnector(token_info.access_token, token_info.instance_url)
        
        if entity_type == "policies":
            results = await connector.search_policies(search_term)
        elif entity_type == "clients":
            results = await connector.search_clients(search_term)
        else:
            results = await connector.search_clients(search_term)
        
    elif query.provider == "hubspot":
        hs_oauth = get_hubspot_oauth_client()
        token_info = await hs_oauth.get_valid_token(query.user_id)
        
        if not token_info:
            raise HTTPException(status_code=401, detail="HubSpot authentication required")
        
        connector = HubSpotConnector(token_info.access_token)
        
        if entity_type == "policies":
            results = await connector.search_deals(search_term)
        elif entity_type == "contacts":
            results = await connector.search_contacts(search_term)
        else:
            results = await connector.search_contacts(search_term)
        
    else:
        raise HTTPException(status_code=400, detail="Invalid CRM provider")
    
    return {
        "results": results,
        "total": len(results),
        "provider": query.provider,
        "entity_type": entity_type,
        "search_term": search_term
    }

