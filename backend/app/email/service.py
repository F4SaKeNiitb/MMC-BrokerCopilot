"""
Email service for sending emails via multiple providers.

Supports SMTP, SendGrid, and Microsoft Graph API.
"""

import os
import smtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod

from ..core.logging import get_logger
from ..core.exceptions import (
    EmailError,
    EmailSendError,
    EmailProviderError as EmailProviderException,
    ConfigurationError,
)
from .models import ScheduledEmail, EmailRecipient, EmailAttachment

logger = get_logger(__name__)


class EmailProviderError(Exception):
    """Base exception for email provider errors."""
    pass


class EmailProvider(ABC):
    """Abstract base class for email providers."""
    
    @abstractmethod
    async def send(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        from_email: str,
        from_name: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send an email and return provider-specific response."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return provider name."""
        pass


class SMTPProvider(EmailProvider):
    """SMTP email provider for standard email sending."""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        use_tls: bool = True,
    ):
        self.host = host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.use_tls = use_tls
    
    def get_name(self) -> str:
        return "smtp"
    
    async def send(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        from_email: str,
        from_name: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
            msg["To"] = ", ".join(to)
            
            if cc:
                msg["Cc"] = ", ".join(cc)
            if reply_to:
                msg["Reply-To"] = reply_to
            
            # Add body parts
            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.get("content", b""))
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{attachment.get("filename", "attachment")}"'
                    )
                    msg.attach(part)
            
            # Get all recipients
            all_recipients = list(to)
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # Send via SMTP
            with smtplib.SMTP(self.host, self.port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(from_email, all_recipients, msg.as_string())
            
            return {
                "success": True,
                "provider": "smtp",
                "message_id": msg["Message-ID"],
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            raise EmailProviderError(f"SMTP send failed: {str(e)}")


class SendGridProvider(EmailProvider):
    """SendGrid email provider for transactional emails."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY", "")
        self.base_url = "https://api.sendgrid.com/v3"
    
    def get_name(self) -> str:
        return "sendgrid"
    
    async def send(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        from_email: str,
        from_name: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via SendGrid API."""
        if not self.api_key:
            raise EmailProviderError("SendGrid API key not configured")
        
        # Build personalizations
        personalizations = [{
            "to": [{"email": email} for email in to],
        }]
        
        if cc:
            personalizations[0]["cc"] = [{"email": email} for email in cc]
        if bcc:
            personalizations[0]["bcc"] = [{"email": email} for email in bcc]
        
        # Build request body
        data = {
            "personalizations": personalizations,
            "from": {"email": from_email},
            "subject": subject,
            "content": [],
        }
        
        if from_name:
            data["from"]["name"] = from_name
        
        if reply_to:
            data["reply_to"] = {"email": reply_to}
        
        if body_text:
            data["content"].append({"type": "text/plain", "value": body_text})
        if body_html:
            data["content"].append({"type": "text/html", "value": body_html})
        
        # Add attachments
        if attachments:
            data["attachments"] = []
            for att in attachments:
                data["attachments"].append({
                    "content": att.get("content_base64", ""),
                    "filename": att.get("filename", "attachment"),
                    "type": att.get("content_type", "application/octet-stream"),
                })
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/mail/send",
                    json=data,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                
                if response.status_code not in (200, 202):
                    raise EmailProviderError(
                        f"SendGrid API error: {response.status_code} - {response.text}"
                    )
                
                return {
                    "success": True,
                    "provider": "sendgrid",
                    "message_id": response.headers.get("X-Message-Id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
        except httpx.RequestError as e:
            logger.error(f"SendGrid request failed: {e}")
            raise EmailProviderError(f"SendGrid request failed: {str(e)}")


class MicrosoftGraphEmailProvider(EmailProvider):
    """Microsoft Graph API email provider for Office 365."""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0"
    
    def get_name(self) -> str:
        return "microsoft_graph"
    
    async def send(
        self,
        to: List[str],
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        from_email: str,
        from_name: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send email via Microsoft Graph API."""
        if not self.access_token:
            raise EmailProviderError("Microsoft Graph access token not provided")
        
        # Build message
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if body_html else "Text",
                "content": body_html or body_text or "",
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in to
            ],
        }
        
        if cc:
            message["ccRecipients"] = [
                {"emailAddress": {"address": email}} for email in cc
            ]
        if bcc:
            message["bccRecipients"] = [
                {"emailAddress": {"address": email}} for email in bcc
            ]
        if reply_to:
            message["replyTo"] = [{"emailAddress": {"address": reply_to}}]
        
        # Add attachments
        if attachments:
            message["attachments"] = []
            for att in attachments:
                message["attachments"].append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att.get("filename", "attachment"),
                    "contentType": att.get("content_type", "application/octet-stream"),
                    "contentBytes": att.get("content_base64", ""),
                })
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/me/sendMail",
                    json={"message": message, "saveToSentItems": True},
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                
                if response.status_code != 202:
                    raise EmailProviderError(
                        f"Microsoft Graph API error: {response.status_code} - {response.text}"
                    )
                
                return {
                    "success": True,
                    "provider": "microsoft_graph",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
        except httpx.RequestError as e:
            logger.error(f"Microsoft Graph request failed: {e}")
            raise EmailProviderError(f"Microsoft Graph request failed: {str(e)}")


class EmailService:
    """
    Email service that manages providers and handles email sending.
    
    Supports multiple providers with automatic fallback.
    """
    
    def __init__(self, primary_provider: str = "smtp"):
        self.providers: Dict[str, EmailProvider] = {}
        self.primary_provider = primary_provider
        self._init_providers()
    
    def _init_providers(self):
        """Initialize available email providers."""
        # Always try to set up SMTP
        try:
            self.providers["smtp"] = SMTPProvider()
        except Exception as e:
            logger.warning(f"SMTP provider init failed: {e}")
        
        # Set up SendGrid if API key is available
        if os.getenv("SENDGRID_API_KEY"):
            try:
                self.providers["sendgrid"] = SendGridProvider()
            except Exception as e:
                logger.warning(f"SendGrid provider init failed: {e}")
    
    def set_microsoft_token(self, access_token: str):
        """Set Microsoft Graph access token for email sending."""
        self.providers["microsoft_graph"] = MicrosoftGraphEmailProvider(access_token)
    
    def get_provider(self, name: Optional[str] = None) -> EmailProvider:
        """Get email provider by name or return primary."""
        provider_name = name or self.primary_provider
        if provider_name not in self.providers:
            raise EmailProviderError(f"Provider '{provider_name}' not available")
        return self.providers[provider_name]
    
    async def send_email(
        self,
        scheduled_email: ScheduledEmail,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a scheduled email using the specified provider.
        
        Falls back to other providers if primary fails.
        """
        # Prepare recipients
        to_recipients = [r.email for r in scheduled_email.recipients if r.type == "to"]
        cc_recipients = [r.email for r in scheduled_email.recipients if r.type == "cc"]
        bcc_recipients = [r.email for r in scheduled_email.recipients if r.type == "bcc"]
        
        # Get providers to try (primary first, then others)
        providers_to_try = []
        if provider_name and provider_name in self.providers:
            providers_to_try.append(provider_name)
        elif self.primary_provider in self.providers:
            providers_to_try.append(self.primary_provider)
        
        # Add remaining providers as fallbacks
        for name in self.providers:
            if name not in providers_to_try:
                providers_to_try.append(name)
        
        if not providers_to_try:
            raise EmailProviderError("No email providers available")
        
        # Try each provider
        last_error = None
        for provider_name in providers_to_try:
            try:
                provider = self.providers[provider_name]
                result = await provider.send(
                    to=to_recipients,
                    subject=scheduled_email.subject,
                    body_html=scheduled_email.body_html,
                    body_text=scheduled_email.body_text,
                    from_email=scheduled_email.from_email,
                    from_name=scheduled_email.from_name,
                    cc=cc_recipients if cc_recipients else None,
                    bcc=bcc_recipients if bcc_recipients else None,
                    reply_to=scheduled_email.reply_to,
                )
                return result
                
            except EmailProviderError as e:
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {e}, trying next...")
                continue
        
        # All providers failed
        raise EmailProviderError(f"All providers failed. Last error: {last_error}")


# Global email service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the global email service instance."""
    global _email_service
    if _email_service is None:
        primary = os.getenv("EMAIL_PROVIDER", "smtp")
        _email_service = EmailService(primary_provider=primary)
    return _email_service
