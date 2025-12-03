"""
Email scheduling API router.

Provides REST endpoints for managing scheduled emails and templates.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime
from jinja2 import Template, TemplateError

from ..core.logging import get_logger
from ..core.exceptions import (
    EmailNotFoundError,
    EmailAlreadySentError,
    EmailTemplateError,
    ValidationError,
)
from .models import (
    ScheduledEmail,
    ScheduleEmailRequest,
    ScheduleEmailResponse,
    EmailListResponse,
    EmailStatsResponse,
    EmailStatus,
    EmailPriority,
    EmailTemplate,
    EmailRecipient,
)
from .store import get_email_store
from .tasks import schedule_email_task, cancel_email_task

logger = get_logger(__name__)

router = APIRouter(prefix="/email", tags=["email"])


# ============================================================================
# Email Scheduling Endpoints
# ============================================================================

@router.post("/schedule", response_model=ScheduleEmailResponse)
async def schedule_email(
    request: ScheduleEmailRequest,
    user_id: str = Query(..., description="Broker user ID"),
    from_email: str = Query(..., description="Sender email address"),
):
    """
    Schedule an email for future delivery.
    
    The email will be queued and sent at the specified time.
    Supports templates with variable substitution.
    """
    logger.info(f"Scheduling email for user {user_id}")
    store = get_email_store()
    
    # Handle template-based emails
    subject = request.subject
    body_html = request.body_html
    body_text = request.body_text
    
    if request.template_id:
        logger.debug(f"Using template: {request.template_id}")
        template = await store.get_template(request.template_id)
        if not template:
            logger.warning(f"Template not found: {request.template_id}")
            raise HTTPException(status_code=404, detail=f"Template {request.template_id} not found")
        
        try:
            # Render template with variables
            variables = request.template_variables or {}
            subject = Template(template.subject_template).render(**variables)
            body_html = Template(template.body_html_template).render(**variables)
            if template.body_text_template:
                body_text = Template(template.body_text_template).render(**variables)
        except TemplateError as e:
            logger.error(f"Template rendering failed: {e}")
            raise HTTPException(status_code=400, detail=f"Template rendering failed: {str(e)}")
    
    if not subject:
        raise HTTPException(status_code=400, detail="Subject is required")
    if not body_html and not body_text:
        raise HTTPException(status_code=400, detail="Email body (HTML or text) is required")
    
    # Create scheduled email
    email = ScheduledEmail(
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        template_id=request.template_id,
        template_variables=request.template_variables,
        from_email=from_email,
        from_name=request.from_name,
        recipients=request.recipients,
        reply_to=request.reply_to,
        scheduled_at=request.scheduled_at,
        timezone=request.timezone,
        recurrence=request.recurrence,
        recurrence_end=request.recurrence_end,
        priority=request.priority,
        policy_id=request.policy_id,
        campaign_id=request.campaign_id,
        tags=request.tags,
        user_id=user_id,
    )
    
    # Save to store
    await store.save_email(email)
    logger.debug(f"Email {email.id} saved to store")
    
    # Schedule the Celery task
    try:
        task_id = schedule_email_task(
            email_id=email.id,
            scheduled_at=email.scheduled_at,
            priority=email.priority,
        )
        logger.info(f"Scheduled email {email.id} with Celery task {task_id}")
    except Exception as e:
        logger.warning(f"Celery task scheduling failed for {email.id} (will use beat scheduler): {e}")
    
    return ScheduleEmailResponse(
        id=email.id,
        status=email.status,
        scheduled_at=email.scheduled_at,
        message=f"Email scheduled for {email.scheduled_at.isoformat()}",
    )


@router.get("/scheduled", response_model=EmailListResponse)
async def list_scheduled_emails(
    user_id: str = Query(..., description="Broker user ID"),
    status: Optional[EmailStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List scheduled emails for a user.
    
    Supports filtering by status and pagination.
    """
    store = get_email_store()
    offset = (page - 1) * page_size
    
    emails = await store.get_emails_by_user(
        user_id=user_id,
        status=status,
        limit=page_size + 1,  # Get one extra to check has_more
        offset=offset,
    )
    
    has_more = len(emails) > page_size
    emails = emails[:page_size]
    
    total = await store.count_emails(user_id=user_id, status=status)
    
    return EmailListResponse(
        emails=emails,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/scheduled/{email_id}", response_model=ScheduledEmail)
async def get_scheduled_email(email_id: str):
    """Get details of a specific scheduled email."""
    store = get_email_store()
    email = await store.get_email(email_id)
    
    if not email:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    
    return email


@router.delete("/scheduled/{email_id}")
async def cancel_scheduled_email(email_id: str):
    """
    Cancel a scheduled email.
    
    Only pending or queued emails can be cancelled.
    """
    store = get_email_store()
    email = await store.get_email(email_id)
    
    if not email:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    
    if email.status not in (EmailStatus.PENDING, EmailStatus.QUEUED):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel email with status {email.status.value}"
        )
    
    # Update status
    await store.update_email_status(email_id, EmailStatus.CANCELLED)
    
    return {"status": "cancelled", "email_id": email_id}


@router.post("/scheduled/{email_id}/send-now")
async def send_email_now(email_id: str):
    """
    Send a scheduled email immediately.
    
    Bypasses the scheduled time and sends right away.
    """
    store = get_email_store()
    email = await store.get_email(email_id)
    
    if not email:
        raise HTTPException(status_code=404, detail=f"Email {email_id} not found")
    
    if email.status not in (EmailStatus.PENDING, EmailStatus.QUEUED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send email with status {email.status.value}"
        )
    
    # Import here to avoid circular import
    from .tasks import send_email_urgent
    
    # Queue for immediate sending
    try:
        send_email_urgent.delay(email_id)
        await store.update_email_status(email_id, EmailStatus.QUEUED)
        return {"status": "queued", "email_id": email_id, "message": "Email queued for immediate delivery"}
    except Exception as e:
        logger.error(f"Failed to queue email {email_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue email for sending")


@router.get("/policy/{policy_id}", response_model=List[ScheduledEmail])
async def get_emails_for_policy(policy_id: str):
    """Get all scheduled emails for a specific policy."""
    store = get_email_store()
    emails = await store.get_emails_by_policy(policy_id)
    return emails


@router.get("/stats", response_model=EmailStatsResponse)
async def get_email_stats(
    user_id: str = Query(..., description="Broker user ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
):
    """
    Get email statistics for a user.
    
    Returns counts of sent, failed, pending emails and engagement rates.
    """
    store = get_email_store()
    
    # Calculate stats
    total_scheduled = await store.count_emails(user_id=user_id)
    total_sent = await store.count_emails(user_id=user_id, status=EmailStatus.SENT)
    total_failed = await store.count_emails(user_id=user_id, status=EmailStatus.FAILED)
    total_pending = await store.count_emails(user_id=user_id, status=EmailStatus.PENDING)
    total_cancelled = await store.count_emails(user_id=user_id, status=EmailStatus.CANCELLED)
    
    # Calculate rates (placeholder - in production would track actual opens/clicks)
    open_rate = 0.0
    click_rate = 0.0
    
    from datetime import timedelta
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)
    
    return EmailStatsResponse(
        total_scheduled=total_scheduled,
        total_sent=total_sent,
        total_failed=total_failed,
        total_pending=total_pending,
        total_cancelled=total_cancelled,
        open_rate=open_rate,
        click_rate=click_rate,
        period_start=period_start,
        period_end=period_end,
    )


# ============================================================================
# Template Endpoints
# ============================================================================

@router.get("/templates", response_model=List[EmailTemplate])
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    user_id: Optional[str] = Query(None, description="Include user's custom templates"),
):
    """
    List available email templates.
    
    Returns system templates and optionally user's custom templates.
    """
    store = get_email_store()
    templates = await store.get_templates(category=category, user_id=user_id)
    return templates


@router.get("/templates/{template_id}", response_model=EmailTemplate)
async def get_template(template_id: str):
    """Get a specific email template."""
    store = get_email_store()
    template = await store.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    
    return template


@router.post("/templates", response_model=EmailTemplate)
async def create_template(
    template: EmailTemplate,
    user_id: str = Query(..., description="Broker user ID"),
):
    """
    Create a custom email template.
    
    Custom templates are owned by the creating user.
    """
    store = get_email_store()
    
    template.user_id = user_id
    template.is_system = False
    
    saved = await store.save_template(template)
    return saved


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """
    Delete a custom template.
    
    System templates cannot be deleted.
    """
    store = get_email_store()
    
    template = await store.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    
    if template.is_system:
        raise HTTPException(status_code=403, detail="System templates cannot be deleted")
    
    await store.delete_template(template_id)
    return {"status": "deleted", "template_id": template_id}


@router.post("/templates/{template_id}/preview")
async def preview_template(
    template_id: str,
    variables: dict = {},
):
    """
    Preview a template with sample variables.
    
    Returns rendered subject and body.
    """
    store = get_email_store()
    template = await store.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    
    try:
        subject = Template(template.subject_template).render(**variables)
        body_html = Template(template.body_html_template).render(**variables)
        body_text = None
        if template.body_text_template:
            body_text = Template(template.body_text_template).render(**variables)
        
        return {
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
            "variables_used": variables,
        }
    except TemplateError as e:
        raise HTTPException(status_code=400, detail=f"Template rendering failed: {str(e)}")
