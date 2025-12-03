"""
Email scheduling data models.

Defines the structure for scheduled emails, templates, and tracking.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class EmailStatus(str, Enum):
    """Status of a scheduled email."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailPriority(str, Enum):
    """Priority level for email delivery."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RecurrenceType(str, Enum):
    """Recurrence pattern for scheduled emails."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class EmailRecipient(BaseModel):
    """Email recipient with optional personalization."""
    email: str
    name: Optional[str] = None
    type: str = "to"  # "to", "cc", "bcc"
    variables: Optional[Dict[str, Any]] = None  # For template personalization


class EmailAttachment(BaseModel):
    """Email attachment metadata."""
    filename: str
    content_type: str
    size_bytes: int
    storage_key: Optional[str] = None  # Reference to stored attachment
    inline: bool = False  # For inline images


class ScheduledEmail(BaseModel):
    """A scheduled email with full configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Core email fields
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    template_id: Optional[str] = None
    template_variables: Optional[Dict[str, Any]] = None
    
    # Recipients
    from_email: str
    from_name: Optional[str] = None
    recipients: List[EmailRecipient]
    reply_to: Optional[str] = None
    
    # Attachments
    attachments: List[EmailAttachment] = []
    
    # Scheduling
    scheduled_at: datetime
    timezone: str = "UTC"
    recurrence: RecurrenceType = RecurrenceType.NONE
    recurrence_end: Optional[datetime] = None
    recurrence_count: Optional[int] = None
    
    # Priority and tracking
    priority: EmailPriority = EmailPriority.NORMAL
    status: EmailStatus = EmailStatus.PENDING
    
    # Metadata
    policy_id: Optional[str] = None  # Link to renewal policy
    user_id: str  # Broker who scheduled this
    campaign_id: Optional[str] = None  # For batch emails
    tags: List[str] = []
    
    # Tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Delivery tracking
    message_id: Optional[str] = None  # Provider message ID
    open_count: int = 0
    click_count: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EmailTemplate(BaseModel):
    """Reusable email template."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    subject_template: str
    body_html_template: str
    body_text_template: Optional[str] = None
    
    # Template metadata
    category: str = "general"  # "renewal", "welcome", "reminder", etc.
    variables: List[str] = []  # Expected variables
    
    # Ownership
    user_id: Optional[str] = None  # None = system template
    is_system: bool = False
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScheduleEmailRequest(BaseModel):
    """API request to schedule an email."""
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    template_id: Optional[str] = None
    template_variables: Optional[Dict[str, Any]] = None
    
    recipients: List[EmailRecipient]
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    
    scheduled_at: datetime
    timezone: str = "UTC"
    recurrence: RecurrenceType = RecurrenceType.NONE
    recurrence_end: Optional[datetime] = None
    
    priority: EmailPriority = EmailPriority.NORMAL
    policy_id: Optional[str] = None
    campaign_id: Optional[str] = None
    tags: List[str] = []


class ScheduleEmailResponse(BaseModel):
    """API response after scheduling an email."""
    id: str
    status: EmailStatus
    scheduled_at: datetime
    message: str


class EmailListResponse(BaseModel):
    """Response for listing scheduled emails."""
    emails: List[ScheduledEmail]
    total: int
    page: int
    page_size: int
    has_more: bool


class EmailStatsResponse(BaseModel):
    """Email statistics for a user or campaign."""
    total_scheduled: int
    total_sent: int
    total_failed: int
    total_pending: int
    total_cancelled: int
    open_rate: float
    click_rate: float
    period_start: datetime
    period_end: datetime
