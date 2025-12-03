"""
In-memory email store for development and testing.

In production, this would be replaced with a proper database (PostgreSQL, MongoDB, etc.)
"""

from typing import Dict, List, Optional
from datetime import datetime
import asyncio
from collections import defaultdict

from ..core.logging import get_logger
from .models import (
    ScheduledEmail, 
    EmailTemplate, 
    EmailStatus, 
    EmailPriority,
    RecurrenceType,
)

logger = get_logger(__name__)


class EmailStore:
    """
    In-memory store for scheduled emails.
    
    Thread-safe using asyncio locks.
    In production, replace with database implementation.
    """
    
    def __init__(self):
        self._emails: Dict[str, ScheduledEmail] = {}
        self._templates: Dict[str, EmailTemplate] = {}
        self._user_emails: Dict[str, List[str]] = defaultdict(list)  # user_id -> email_ids
        self._policy_emails: Dict[str, List[str]] = defaultdict(list)  # policy_id -> email_ids
        self._lock = asyncio.Lock()
        
        # Initialize with some default templates
        self._init_default_templates()
    
    def _init_default_templates(self):
        """Initialize default email templates."""
        default_templates = [
            EmailTemplate(
                id="renewal_reminder_30",
                name="30-Day Renewal Reminder",
                description="Reminder sent 30 days before policy expiration",
                subject_template="Policy Renewal Reminder: {{policy_number}} expires in 30 days",
                body_html_template="""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #1a365d;">Policy Renewal Reminder</h2>
                        <p>Dear {{client_name}},</p>
                        <p>This is a friendly reminder that your policy <strong>{{policy_number}}</strong> 
                        is set to expire on <strong>{{expiry_date}}</strong>.</p>
                        <div style="background: #f7fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="margin-top: 0;">Policy Details</h3>
                            <p><strong>Policy Type:</strong> {{policy_type}}</p>
                            <p><strong>Current Premium:</strong> ${{premium}}</p>
                            <p><strong>Expiration Date:</strong> {{expiry_date}}</p>
                        </div>
                        <p>Please contact your broker to discuss renewal options.</p>
                        <p>Best regards,<br>{{broker_name}}</p>
                    </div>
                """,
                body_text_template="""
                    Policy Renewal Reminder
                    
                    Dear {{client_name}},
                    
                    This is a friendly reminder that your policy {{policy_number}} 
                    is set to expire on {{expiry_date}}.
                    
                    Policy Details:
                    - Policy Type: {{policy_type}}
                    - Current Premium: ${{premium}}
                    - Expiration Date: {{expiry_date}}
                    
                    Please contact your broker to discuss renewal options.
                    
                    Best regards,
                    {{broker_name}}
                """,
                category="renewal",
                variables=["client_name", "policy_number", "expiry_date", "policy_type", "premium", "broker_name"],
                is_system=True,
            ),
            EmailTemplate(
                id="renewal_reminder_7",
                name="7-Day Renewal Reminder",
                description="Urgent reminder sent 7 days before policy expiration",
                subject_template="URGENT: Policy {{policy_number}} expires in 7 days",
                body_html_template="""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: #fc8181; color: white; padding: 10px 20px; border-radius: 8px 8px 0 0;">
                            <h2 style="margin: 0;">⚠️ Urgent: Policy Expiring Soon</h2>
                        </div>
                        <div style="border: 2px solid #fc8181; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
                            <p>Dear {{client_name}},</p>
                            <p><strong>Your policy {{policy_number}} will expire in just 7 days!</strong></p>
                            <p>To avoid any lapse in coverage, please contact us immediately to discuss your renewal.</p>
                            <div style="background: #fff5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                                <p style="margin: 0;"><strong>Expiration Date:</strong> {{expiry_date}}</p>
                                <p style="margin: 10px 0 0 0;"><strong>Current Premium:</strong> ${{premium}}</p>
                            </div>
                            <a href="{{renewal_link}}" style="display: inline-block; background: #2b6cb0; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 10px;">
                                Review Renewal Options
                            </a>
                            <p style="margin-top: 20px;">Best regards,<br>{{broker_name}}</p>
                        </div>
                    </div>
                """,
                category="renewal",
                variables=["client_name", "policy_number", "expiry_date", "premium", "renewal_link", "broker_name"],
                is_system=True,
            ),
            EmailTemplate(
                id="renewal_quote",
                name="Renewal Quote",
                description="Send renewal quote to client",
                subject_template="Your Renewal Quote for Policy {{policy_number}}",
                body_html_template="""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #1a365d;">Your Renewal Quote</h2>
                        <p>Dear {{client_name}},</p>
                        <p>Thank you for your continued trust in our services. Please find below 
                        your renewal quote for policy {{policy_number}}.</p>
                        <div style="background: #ebf8ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2b6cb0;">
                            <h3 style="margin-top: 0; color: #2b6cb0;">Quote Summary</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0;">Policy Type:</td>
                                    <td style="padding: 8px 0; text-align: right;"><strong>{{policy_type}}</strong></td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">Current Premium:</td>
                                    <td style="padding: 8px 0; text-align: right;">${{current_premium}}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">Renewal Premium:</td>
                                    <td style="padding: 8px 0; text-align: right; font-size: 1.2em;"><strong>${{renewal_premium}}</strong></td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">Change:</td>
                                    <td style="padding: 8px 0; text-align: right;">{{premium_change}}</td>
                                </tr>
                            </table>
                        </div>
                        <p>This quote is valid until {{quote_expiry}}.</p>
                        <a href="{{accept_link}}" style="display: inline-block; background: #38a169; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                            Accept Quote
                        </a>
                        <p style="margin-top: 20px;">If you have any questions, please don't hesitate to reach out.</p>
                        <p>Best regards,<br>{{broker_name}}</p>
                    </div>
                """,
                category="renewal",
                variables=["client_name", "policy_number", "policy_type", "current_premium", "renewal_premium", "premium_change", "quote_expiry", "accept_link", "broker_name"],
                is_system=True,
            ),
            EmailTemplate(
                id="welcome_client",
                name="Welcome New Client",
                description="Welcome email for new clients",
                subject_template="Welcome to {{company_name}} - Your Insurance Partner",
                body_html_template="""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #1a365d;">Welcome Aboard! 🎉</h2>
                        <p>Dear {{client_name}},</p>
                        <p>Welcome to {{company_name}}! We're thrilled to have you as a client.</p>
                        <p>Your dedicated broker is <strong>{{broker_name}}</strong>, who will be your 
                        main point of contact for all insurance matters.</p>
                        <div style="background: #f7fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="margin-top: 0;">Getting Started</h3>
                            <ul>
                                <li>Review your policy documents</li>
                                <li>Save our contact information</li>
                                <li>Schedule an annual review</li>
                            </ul>
                        </div>
                        <p>We're here to help protect what matters most to you.</p>
                        <p>Best regards,<br>{{broker_name}}<br>{{broker_phone}}<br>{{broker_email}}</p>
                    </div>
                """,
                category="general",
                variables=["client_name", "company_name", "broker_name", "broker_phone", "broker_email"],
                is_system=True,
            ),
        ]
        
        for template in default_templates:
            self._templates[template.id] = template
    
    # =========================================================================
    # Email CRUD Operations
    # =========================================================================
    
    async def save_email(self, email: ScheduledEmail) -> ScheduledEmail:
        """Save or update a scheduled email."""
        async with self._lock:
            is_new = email.id not in self._emails
            email.updated_at = datetime.utcnow()
            self._emails[email.id] = email
            
            # Update indexes
            if email.user_id and email.id not in self._user_emails[email.user_id]:
                self._user_emails[email.user_id].append(email.id)
            if email.policy_id and email.id not in self._policy_emails[email.policy_id]:
                self._policy_emails[email.policy_id].append(email.id)
            
            action = "Created" if is_new else "Updated"
            logger.info(
                f"{action} scheduled email",
                extra={
                    "email_id": email.id,
                    "user_id": email.user_id,
                    "status": email.status.value,
                    "scheduled_at": email.scheduled_at.isoformat() if email.scheduled_at else None,
                }
            )
            
            return email
    
    async def get_email(self, email_id: str) -> Optional[ScheduledEmail]:
        """Get a scheduled email by ID."""
        email = self._emails.get(email_id)
        if email:
            logger.debug(f"Retrieved email {email_id}")
        else:
            logger.debug(f"Email {email_id} not found")
        return email
    
    async def delete_email(self, email_id: str) -> bool:
        """Delete a scheduled email."""
        async with self._lock:
            email = self._emails.pop(email_id, None)
            if email:
                # Clean up indexes
                if email.user_id and email_id in self._user_emails[email.user_id]:
                    self._user_emails[email.user_id].remove(email_id)
                if email.policy_id and email_id in self._policy_emails[email.policy_id]:
                    self._policy_emails[email.policy_id].remove(email_id)
                logger.info(
                    f"Deleted scheduled email",
                    extra={
                        "email_id": email_id,
                        "user_id": email.user_id,
                        "status": email.status.value,
                    }
                )
                return True
            logger.warning(f"Attempted to delete non-existent email {email_id}")
            return False
    
    async def get_emails_by_user(
        self, 
        user_id: str, 
        status: Optional[EmailStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ScheduledEmail]:
        """Get scheduled emails for a user."""
        logger.debug(
            f"Fetching emails for user",
            extra={
                "user_id": user_id,
                "status": status.value if status else None,
                "limit": limit,
                "offset": offset,
            }
        )
        
        email_ids = self._user_emails.get(user_id, [])
        emails = [self._emails[eid] for eid in email_ids if eid in self._emails]
        
        if status:
            emails = [e for e in emails if e.status == status]
        
        # Sort by scheduled_at descending
        emails.sort(key=lambda e: e.scheduled_at, reverse=True)
        
        result = emails[offset:offset + limit]
        logger.debug(
            f"Found {len(result)} emails for user {user_id}",
            extra={"total_matching": len(emails)}
        )
        
        return result
    
    async def get_emails_by_policy(self, policy_id: str) -> List[ScheduledEmail]:
        """Get scheduled emails for a policy."""
        logger.debug(f"Fetching emails for policy {policy_id}")
        email_ids = self._policy_emails.get(policy_id, [])
        emails = [self._emails[eid] for eid in email_ids if eid in self._emails]
        emails.sort(key=lambda e: e.scheduled_at, reverse=True)
        logger.debug(f"Found {len(emails)} emails for policy {policy_id}")
        return emails
    
    async def get_pending_emails(
        self, 
        before: datetime,
        limit: int = 100,
    ) -> List[ScheduledEmail]:
        """Get pending emails that are due to be sent."""
        logger.debug(f"Fetching pending emails due before {before}")
        
        pending = [
            email for email in self._emails.values()
            if email.status == EmailStatus.PENDING
            and email.scheduled_at <= before
        ]
        
        # Sort by priority (urgent first) then by scheduled time
        priority_order = {
            EmailPriority.URGENT: 0,
            EmailPriority.HIGH: 1,
            EmailPriority.NORMAL: 2,
            EmailPriority.LOW: 3,
        }
        pending.sort(key=lambda e: (priority_order.get(e.priority, 2), e.scheduled_at))
        
        result = pending[:limit]
        logger.debug(
            f"Found {len(result)} pending emails",
            extra={
                "total_pending": len(pending),
                "limit": limit,
                "urgent_count": sum(1 for e in result if e.priority == EmailPriority.URGENT),
            }
        )
        
        return result
    
    async def update_email_status(
        self,
        email_id: str,
        status: EmailStatus,
        error_message: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Optional[ScheduledEmail]:
        """Update email status after send attempt."""
        async with self._lock:
            email = self._emails.get(email_id)
            if email:
                old_status = email.status
                email.status = status
                email.updated_at = datetime.utcnow()
                
                if status == EmailStatus.SENT:
                    email.sent_at = datetime.utcnow()
                if error_message:
                    email.error_message = error_message
                    email.retry_count += 1
                if message_id:
                    email.message_id = message_id
                
                logger.info(
                    f"Email status updated",
                    extra={
                        "email_id": email_id,
                        "old_status": old_status.value,
                        "new_status": status.value,
                        "retry_count": email.retry_count,
                        "has_error": bool(error_message),
                    }
                )
                
                return email
            
            logger.warning(f"Attempted to update status of non-existent email {email_id}")
            return None
    
    async def count_emails(
        self, 
        user_id: Optional[str] = None,
        status: Optional[EmailStatus] = None,
    ) -> int:
        """Count emails matching criteria."""
        emails = self._emails.values()
        
        if user_id:
            emails = [e for e in emails if e.user_id == user_id]
        if status:
            emails = [e for e in emails if e.status == status]
        
        count = len(list(emails))
        logger.debug(
            f"Counted {count} emails",
            extra={
                "user_id": user_id,
                "status": status.value if status else None,
            }
        )
        return count
    
    # =========================================================================
    # Template Operations
    # =========================================================================
    
    async def get_template(self, template_id: str) -> Optional[EmailTemplate]:
        """Get an email template by ID."""
        template = self._templates.get(template_id)
        if template:
            logger.debug(f"Retrieved template {template_id}")
        else:
            logger.debug(f"Template {template_id} not found")
        return template
    
    async def get_templates(
        self, 
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        include_system: bool = True,
    ) -> List[EmailTemplate]:
        """Get email templates."""
        logger.debug(
            "Fetching templates",
            extra={
                "category": category,
                "user_id": user_id,
                "include_system": include_system,
            }
        )
        
        templates = list(self._templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if not include_system:
            templates = [t for t in templates if not t.is_system]
        elif user_id:
            templates = [t for t in templates if t.is_system or t.user_id == user_id]
        
        logger.debug(f"Found {len(templates)} templates")
        return templates
    
    async def save_template(self, template: EmailTemplate) -> EmailTemplate:
        """Save or update a template."""
        async with self._lock:
            is_new = template.id not in self._templates
            template.updated_at = datetime.utcnow()
            self._templates[template.id] = template
            
            action = "Created" if is_new else "Updated"
            logger.info(
                f"{action} email template",
                extra={
                    "template_id": template.id,
                    "name": template.name,
                    "category": template.category,
                    "is_system": template.is_system,
                }
            )
            return template
    
    async def delete_template(self, template_id: str) -> bool:
        """Delete a template (system templates cannot be deleted)."""
        async with self._lock:
            template = self._templates.get(template_id)
            if template and not template.is_system:
                del self._templates[template_id]
                logger.info(
                    f"Deleted email template",
                    extra={
                        "template_id": template_id,
                        "name": template.name,
                    }
                )
                return True
            
            if template and template.is_system:
                logger.warning(f"Attempted to delete system template {template_id}")
            else:
                logger.warning(f"Attempted to delete non-existent template {template_id}")
            return False


# Global store instance
_email_store: Optional[EmailStore] = None


def get_email_store() -> EmailStore:
    """Get or create the global email store instance."""
    global _email_store
    if _email_store is None:
        logger.info("Initializing email store")
        _email_store = EmailStore()
        logger.info(
            "Email store initialized",
            extra={"default_template_count": len(_email_store._templates)}
        )
    return _email_store
